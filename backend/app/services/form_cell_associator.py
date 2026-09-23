"""Step 2: geometry-aware form-cell association on normalized lines.

Sits between the line/region model and candidate routing:

  LogicalLine regions
    → FormCellAssociation (one primary label owner per value)
    → candidate_router (category + confidence + validation)

Does not persist anything and does not call an LLM. Original line
coordinates and parent_block_id are preserved on every association.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.contract_summary_fields import match_label, validate_value
from app.services.line_model import LogicalLine

# Numbered government-form item: "2. CONTRACT NUMBER", "10A. NAME", "15B. TELEPHONE"
_NUMBERED_FORM_LABEL = re.compile(
    r"^\s*(?P<item>\d{1,2}[A-Z]?)\.\s+(?P<label>.+?)\s*$",
    re.IGNORECASE,
)
# Letter-only SF33 sub-items under a parent item (e.g. 10. FOR INFORMATION CALL):
# "A. NAME", "B. TELEPHONE", "C. E-MAIL ADDRESS". Must not treat TOC/section
# headers like "B. SUPPLIES OR SERVICES..." as form labels.
_LETTER_FORM_SUBITEM = re.compile(
    r"^\s*(?P<item>[A-Z])\.\s+(?P<label>.+?)\s*$",
    re.IGNORECASE,
)

_MAX_BELOW_GAP = 28.0
_MAX_RIGHT_GAP = 220.0
_COLUMN_ALIGN_TOLERANCE = 18.0
_AMBIGUITY_MARGIN = 12.0
# How far past a label's right edge a below-value may still count as
# "under this cell" (SF33 packs AREA CODE / NUMBER / EXT under TELEPHONE).
_UNDER_CELL_X_PAD = 50.0

# Form sub-headers that are not themselves values.
_FORM_SUBHEADER_TOKENS = frozenset(
    {
        "area code",
        "number",
        "ext",
        "ext.",
        "extension",
        "code",
        "(x)",
        "sec.",
        "description",
        "page(s)",
        "(hour)",
        "(date)",
    }
)

_PHONE_DIGIT_FRAG = re.compile(r"^[\d()\-.\s/]{3,20}$")


@dataclass(frozen=True)
class FormCellAssociation:
    """One label owning at most one primary value region."""

    page_number: int
    item_number: str | None
    label_text: str
    field_key: str | None
    value_text: str | None
    label_line: LogicalLine
    value_line: LogicalLine | None
    association: str  # below_label | right_of_label | same_line | unassociated | ambiguous
    confidence: float
    reason_codes: list[str] = field(default_factory=list)
    alternate_values: tuple[str, ...] = ()


def _looks_like_prose(text: str) -> bool:
    words = text.split()
    if len(words) >= 12:
        return True
    lower = text.lower()
    return any(
        token in lower
        for token in (
            "shall ",
            "whether or not",
            "the contractor",
            "in accordance with",
        )
    )


def _looks_like_form_label_body(body: str) -> bool:
    """True for SF33-style short labels; false for numbered prose list items.

    Confirmed false positive: ``3. OCO-directed non-standard...`` matched the
    numbered-item regex and then owned the next heading as a field value.
    """

    text = body.strip()
    words = text.split()
    if not words or len(words) > 8 or len(text) > 70:
        return False
    if _looks_like_prose(text):
        return False
    if match_label(text) is not None:
        return True
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio >= 0.55 and len(words) <= 6


def _is_label_line(line: LogicalLine) -> bool:
    text = line.text.strip()
    if len(text.split()) > 12:
        return False
    numbered = _NUMBERED_FORM_LABEL.match(text)
    if numbered is not None:
        return _looks_like_form_label_body(numbered.group("label"))
    letter = _LETTER_FORM_SUBITEM.match(text)
    if letter is not None:
        body = letter.group("label")
        # Vocabulary gate — avoids TOC "B. SUPPLIES OR SERVICES..." labels.
        return match_label(body) is not None or match_label(text) is not None
    # Short unnumbered labels only when vocabulary matches.
    return match_label(text) is not None and len(text) <= 60


def _parse_form_item(text: str) -> tuple[str | None, str]:
    """Return (item_number, label_body) for a form label line."""

    numbered = _NUMBERED_FORM_LABEL.match(text)
    if numbered and _looks_like_form_label_body(numbered.group("label")):
        return numbered.group("item"), numbered.group("label")
    letter = _LETTER_FORM_SUBITEM.match(text)
    if letter and (
        match_label(letter.group("label")) is not None
        or match_label(text) is not None
    ):
        return letter.group("item"), letter.group("label")
    return None, text


def _is_value_candidate(line: LogicalLine) -> bool:
    text = line.text.strip()
    if not text or _is_label_line(line):
        return False
    if text.lower().rstrip(".") in _FORM_SUBHEADER_TOKENS:
        return False
    if _looks_like_prose(text):
        return False
    if len(text) > 180:
        return False
    return True


def _column_aligned(a: LogicalLine, b: LogicalLine) -> bool:
    return abs(a.x0 - b.x0) <= _COLUMN_ALIGN_TOLERANCE


def _under_label_cell(label: LogicalLine, value: LogicalLine) -> bool:
    """True when value sits under the label's horizontal cell span.

    Prefer this for packed SF33 sub-fields where left-edge column
    alignment alone rejects AREA CODE / NUMBER fragments under TELEPHONE.
    """

    left = label.x0 - _UNDER_CELL_X_PAD
    right = label.x1 + _UNDER_CELL_X_PAD
    value_mid = (value.x0 + value.x1) / 2.0
    return left <= value_mid <= right or (
        value.x0 <= right and value.x1 >= left
    )


def _score_below(label: LogicalLine, value: LogicalLine) -> float | None:
    if value.y0 < label.y1 - 1.0:
        return None
    gap = value.y0 - label.y1
    if gap > _MAX_BELOW_GAP:
        return None
    if _column_aligned(label, value):
        return gap
    if _under_label_cell(label, value):
        return gap + 8.0  # slightly prefer true column alignment
    return None


def _compose_telephone(
    *,
    label: LogicalLine,
    values: list[LogicalLine],
    claimed: set[int],
) -> tuple[str, list[LogicalLine]] | None:
    """Join AREA CODE + NUMBER (+ EXT) fragments under a telephone label."""

    frags: list[LogicalLine] = []
    for value in values:
        if id(value) in claimed:
            continue
        if value.page_number != label.page_number:
            continue
        if value.y0 < label.y1 - 1.0:
            continue
        if value.y0 - label.y1 > _MAX_BELOW_GAP + 8.0:
            continue
        if not _under_label_cell(label, value):
            continue
        text = value.text.strip()
        if not _PHONE_DIGIT_FRAG.match(text):
            continue
        # Reject lone page numbers / years when nothing else is nearby.
        digits = re.sub(r"\D", "", text)
        if len(digits) < 3:
            continue
        frags.append(value)

    if not frags:
        return None

    frags.sort(key=lambda line: (line.y0, line.x0))
    # Prefer a single horizontal band (same y).
    band_y = frags[0].y0
    band = [f for f in frags if abs(f.y0 - band_y) <= 6.0]
    composed = "-".join(f.text.strip() for f in band)
    # Normalize "240-541-1679" style
    digits = re.sub(r"\D", "", composed)
    if len(digits) == 10:
        normalized = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    elif len(digits) == 7:
        normalized = f"{digits[:3]}-{digits[3:]}"
    else:
        normalized = composed

    result = validate_value("telephone", normalized)
    if not result.is_valid:
        # Also try raw joined digits with a leading area-code join.
        alt = composed.replace(" ", "")
        result = validate_value("telephone", alt)
        if not result.is_valid:
            return None
        normalized = alt

    return normalized, band


def _score_right(label: LogicalLine, value: LogicalLine) -> float | None:
    if value.x0 < label.x1 - 2.0:
        return None
    # Roughly same horizontal band.
    label_mid = (label.y0 + label.y1) / 2.0
    value_mid = (value.y0 + value.y1) / 2.0
    if abs(label_mid - value_mid) > max(label.y1 - label.y0, 10.0) * 1.5:
        return None
    gap = value.x0 - label.x1
    if gap > _MAX_RIGHT_GAP:
        return None
    return gap + 40.0  # Prefer below associations slightly.


def _score_same_line(label: LogicalLine, value: LogicalLine) -> float | None:
    """Label and value on the same logical line after a separator."""

    if label is not value:
        return None
    if ":" not in label.text and "\t" not in label.text:
        return None
    return 0.0


def associate_form_cells(
    *,
    lines: list[LogicalLine],
    claimed_value_ids: set[int] | None = None,
) -> list[FormCellAssociation]:
    """Pair numbered/gov-form labels with their primary owned values.

    Each value line may be claimed by at most one label. When two validated
    candidates remain nearly equidistant, the association is marked
    ambiguous and both values are preserved in ``alternate_values``.
    """

    claimed = set(claimed_value_ids or ())
    labels: list[LogicalLine] = [line for line in lines if _is_label_line(line)]
    values: list[LogicalLine] = [line for line in lines if _is_value_candidate(line)]

    associations: list[FormCellAssociation] = []

    for label in labels:
        item_number, label_body = _parse_form_item(label.text)
        field_key = match_label(label_body) or match_label(label.text)

        scored: list[tuple[float, LogicalLine, str]] = []
        for value in values:
            if id(value) in claimed:
                continue
            for scorer, kind in (
                (_score_below, "below_label"),
                (_score_right, "right_of_label"),
            ):
                score = scorer(label, value)
                if score is not None:
                    scored.append((score, value, kind))

        # Same-line "LABEL: value" pattern — only for short, recognized labels.
        if ":" in label.text:
            parts = label.text.split(":", 1)
            left = parts[0].strip()
            right = parts[1].strip() if len(parts) == 2 else ""
            if (
                right
                and not _looks_like_prose(right)
                and len(left.split()) <= 6
                and match_label(left) is not None
            ):
                synthetic = LogicalLine(
                    page_number=label.page_number,
                    parent_block_index=label.parent_block_index,
                    line_index=label.line_index,
                    text=right,
                    x0=(label.x0 + label.x1) / 2.0,
                    y0=label.y0,
                    x1=label.x1,
                    y1=label.y1,
                    extraction_method=label.extraction_method,
                    source=label.source,
                    confidence=label.confidence,
                )
                scored.append((0.0, synthetic, "same_line"))

        scored.sort(key=lambda item: item[0])

        if field_key is not None:
            if field_key == "telephone":
                composed = _compose_telephone(
                    label=label, values=values, claimed=claimed
                )
                if composed is not None:
                    phone_text, band = composed
                    for frag in band:
                        claimed.add(id(frag))
                    synthetic = LogicalLine(
                        page_number=label.page_number,
                        parent_block_index=label.parent_block_index,
                        line_index=label.line_index,
                        text=phone_text,
                        x0=min(f.x0 for f in band),
                        y0=min(f.y0 for f in band),
                        x1=max(f.x1 for f in band),
                        y1=max(f.y1 for f in band),
                        extraction_method=label.extraction_method,
                        source=label.source,
                        confidence=label.confidence,
                    )
                    associations.append(
                        FormCellAssociation(
                            page_number=label.page_number,
                            item_number=item_number,
                            label_text=label_body.strip(),
                            field_key=field_key,
                            value_text=phone_text,
                            label_line=label,
                            value_line=synthetic,
                            association="below_label",
                            confidence=0.85,
                            reason_codes=[
                                "form_cell_owned",
                                "composed_multipart_phone",
                                "semantic_validation_passed",
                                "valid_phone_shape",
                            ],
                        )
                    )
                    continue

            validated: list[tuple[float, LogicalLine, str, str]] = []
            rejected: list[str] = []
            for score, value, kind in scored:
                result = validate_value(field_key, value.text)
                if result.is_valid:
                    validated.append((score, value, kind, result.reason))
                else:
                    rejected.append(f"{value.text!r}:{result.reason}")

            if not validated:
                associations.append(
                    FormCellAssociation(
                        page_number=label.page_number,
                        item_number=item_number,
                        label_text=label_body.strip(),
                        field_key=field_key,
                        value_text=None,
                        label_line=label,
                        value_line=None,
                        association="unassociated",
                        confidence=0.35,
                        reason_codes=[
                            "no_semantically_valid_value",
                            *rejected[:3],
                        ],
                    )
                )
                continue

            if (
                len(validated) >= 2
                and (validated[1][0] - validated[0][0]) < _AMBIGUITY_MARGIN
            ):
                alts = tuple(v.text for _, v, _, _ in validated[:3])
                associations.append(
                    FormCellAssociation(
                        page_number=label.page_number,
                        item_number=item_number,
                        label_text=label_body.strip(),
                        field_key=field_key,
                        value_text=None,
                        label_line=label,
                        value_line=None,
                        association="ambiguous",
                        confidence=0.5,
                        reason_codes=["ambiguous_multiple_validated_candidates"],
                        alternate_values=alts,
                    )
                )
                continue

            score, best, kind, reason = validated[0]
            claimed.add(id(best))
            associations.append(
                FormCellAssociation(
                    page_number=label.page_number,
                    item_number=item_number,
                    label_text=label_body.strip(),
                    field_key=field_key,
                    value_text=best.text,
                    label_line=label,
                    value_line=best,
                    association=kind,
                    confidence=0.85,
                    reason_codes=[
                        "form_cell_owned",
                        kind,
                        "semantic_validation_passed",
                        reason,
                    ],
                )
            )
            continue

        # Unrecognized label vocabulary: still allow geometric ownership
        # so the router can emit GENERAL_ACCEPTED_FIELD / QA_REVIEW.
        if not scored:
            associations.append(
                FormCellAssociation(
                    page_number=label.page_number,
                    item_number=item_number,
                    label_text=label_body.strip(),
                    field_key=None,
                    value_text=None,
                    label_line=label,
                    value_line=None,
                    association="unassociated",
                    confidence=0.4,
                    reason_codes=["unrecognized_label_no_value"],
                )
            )
            continue

        score, best, kind = scored[0]
        claimed.add(id(best))
        associations.append(
            FormCellAssociation(
                page_number=label.page_number,
                item_number=item_number,
                label_text=label_body.strip(),
                field_key=None,
                value_text=best.text,
                label_line=label,
                value_line=best,
                association=kind,
                confidence=0.7,
                reason_codes=["form_cell_owned", kind, "unrecognized_field_vocabulary"],
            )
        )

    return associations
