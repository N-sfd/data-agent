"""Generic form-label rejection for scanned government/business forms.

A candidate such as "3. SOLICITATION NUMBER" — or a mashup of several
labels — must never be accepted as another field's *value* merely because
OCR confidence was high.

Wrong-but-confident is worse than blank.
"""

from __future__ import annotations

import re

# Single SF-33 / OF-347 style marker line.
_NUMBERED_LABEL = re.compile(
    r"^(?:\d{1,2}\.|[A-Z]\.)\s+[A-Z][A-Z0-9 /#.'\-]{1,80}$"
)
_BARE_FORM_LABEL = re.compile(
    r"^(?:"
    r"SOLICITATION(?:\s+NUMBER)?|"
    r"TYPE OF SOLICITATION|"
    r"REQUISITION(?:/PURCHASE)?(?:\s+NUMBER)?|"
    r"CONTRACT(?:\s+NUMBER|\s+NO\.?)?|"
    r"ISSUED BY|ISSUED TO|SHIP TO|"
    r"DATE ISSUED|EFFECTIVE DATE|"
    r"NAME|TELEPHONE|EMAIL|ADDRESS|NUMBER|NO\.?|CODE|DATE|TYPE|"
    r"OFFEROR|AWARD|"
    r"PAGE\s+\d+\s+OF\s+\d+"
    r")$"
)

# Field markers anywhere (lettered or numbered form cells).
_FIELD_MARKER = re.compile(r"(?:^|[\s/|]+)\d{1,2}\.\s+[A-Z]{2,}")
_LETTERED_MARKER = re.compile(r"(?:^|[\s/|]+)[A-Z]\.\s+[A-Z]{2,}")

# Contaminated multi-cell OCR joined by slash or pipe.
_MULTI_LABEL_MASHUP = re.compile(
    r"(?:\d{1,2}\.|[A-Z]\.)\s+[A-Z][A-Z0-9 /#.'\-]{1,40}"
    r"(?:\s*[|/]\s*(?:\d{1,2}\.|[A-Z]\.)\s+[A-Z])"
)

_SENTENCE_LIKE = re.compile(r"[.!?].*\s+\w+")
_ID_THEN_PROSE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._/\-]{4,40}\s*[,;:]\s+\S+"
)
_CODE_THEN_NEXT_FIELD = re.compile(
    r"^CODE\s+\S+.+(?:\d{1,2}\.|[A-Z]\.)\s+[A-Z]{2,}",
    re.IGNORECASE,
)

# Compact identifiers we accept; everything else with spaces is suspect
# when the field semantics imply an ID.
_COMPACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]{2,47}$")

_IDENTIFIER_TYPES = frozenset(
    {
        "identifier",
        "id",
        "contract_number",
        "solicitation_number",
        "contract_no",
        "requisition_number",
    }
)
_DATE_TYPES = frozenset({"date", "effective_date", "date_issued"})
_NAME_TYPES = frozenset({"name", "text", "party", None})


def count_field_markers(value: str) -> int:
    text = " ".join(str(value).strip().split())
    if not text:
        return 0
    numbered = len(_FIELD_MARKER.findall(" " + text))
    lettered = len(_LETTERED_MARKER.findall(" " + text))
    # Avoid double-counting the leading marker when both patterns fire.
    leading = 1 if re.match(r"^(?:\d{1,2}\.|[A-Z]\.)\s+[A-Z]", text) else 0
    return max(numbered + lettered, leading)


def looks_like_form_label(value: str | None) -> bool:
    if value is None:
        return True
    text = " ".join(str(value).strip().split())
    if not text:
        return True
    if _NUMBERED_LABEL.match(text):
        return True
    if _BARE_FORM_LABEL.match(text.upper()):
        return True
    if _MULTI_LABEL_MASHUP.search(text):
        return True
    if count_field_markers(text) >= 2:
        return True
    # Long Title-Case phrases with no digits are usually labels, not IDs.
    if (
        len(text) > 28
        and not any(ch.isdigit() for ch in text)
        and text == text.title()
    ):
        return True
    return False


def looks_like_identifier_sentence(value: str | None) -> bool:
    """Reject prose/sentences/labels proposed as compact identifiers."""

    if value is None:
        return True
    text = " ".join(str(value).strip().split())
    if not text:
        return True
    if looks_like_form_label(text):
        return True
    if count_field_markers(text) >= 1 and not _COMPACT_ID.match(
        text.replace(" ", "")
    ):
        # "CODE 47QRCA 8. ADDRESS…" or any marker-bearing non-compact string.
        return True
    if _CODE_THEN_NEXT_FIELD.match(text):
        return True
    if _ID_THEN_PROSE.match(text):
        return True
    if len(text) > 40 and " " in text:
        return True
    if _SENTENCE_LIKE.search(text):
        return True
    if re.search(r"\s+(?:\d{1,2}\.|[A-Z]\.)\s+[A-Z]{2,}", text):
        return True
    if "/" in text and count_field_markers(text) >= 1:
        return True
    return False


def looks_like_narrative_fragment(value: str | None) -> bool:
    """Reject mid-sentence OCR slices proposed as dates/names/IDs."""

    if value is None:
        return True
    text = " ".join(str(value).strip().split())
    if not text:
        return True
    lowered = text.lower()
    if lowered.startswith(("of ", "to ", "the ", "and ", "or ", "for ", "any ")):
        return True
    if " of any " in lowered or " current as of " in lowered:
        return True
    return False


def reject_as_field_value(
    value: str | None,
    *,
    value_type: str | None = None,
    known_labels: frozenset[str] | None = None,
    field_key: str | None = None,
) -> str | None:
    """Return a rejection reason, or None if the value is acceptable.

    Applies to *all* discovered field types — not only identifiers.
    """

    if value is None or not str(value).strip():
        return "empty_value"
    text = " ".join(str(value).strip().split())
    if known_labels and text.lower() in {label.lower() for label in known_labels}:
        return "matches_known_label"
    if looks_like_form_label(text):
        return "looks_like_form_label"
    # Leftover label tokens after a failed split ("NUMBER", "NO.", "CODE").
    if text.upper() in {
        "NUMBER",
        "NO",
        "NO.",
        "CODE",
        "DATE",
        "TYPE",
        "NAME",
        "ADDRESS",
        "TELEPHONE",
        "EMAIL",
    }:
        return "bare_label_token"
    if count_field_markers(text) >= 2:
        return "multi_label_mashup"
    if _MULTI_LABEL_MASHUP.search(text):
        return "multi_label_mashup"
    if _CODE_THEN_NEXT_FIELD.match(text):
        return "cross_cell_contamination"

    effective_type = (value_type or "").lower() or None
    key = (field_key or "").lower()

    if (
        effective_type in _IDENTIFIER_TYPES
        or key in _IDENTIFIER_TYPES
        or key.endswith("_number")
        or key.endswith("_no")
        or key.endswith("_id")
    ):
        if looks_like_identifier_sentence(text):
            return "identifier_looks_like_prose_or_label"
        if not _COMPACT_ID.match(text.replace(" ", "")):
            if " " in text or "," in text:
                return "identifier_not_compact"

    if effective_type in _DATE_TYPES or "date" in key:
        if looks_like_form_label(text) or count_field_markers(text) >= 1:
            return "date_looks_like_form_label"
        if looks_like_narrative_fragment(text):
            return "date_looks_like_narrative"

    if effective_type in {"name"} or key in {"name", "issued_by", "ship_to"}:
        if looks_like_form_label(text) or count_field_markers(text) >= 1:
            return "name_looks_like_form_heading"
        if looks_like_narrative_fragment(text):
            return "name_looks_like_narrative"

    if looks_like_narrative_fragment(text) and effective_type not in {
        "text",
        "address",
        "clause",
    }:
        return "narrative_fragment"

    return None
