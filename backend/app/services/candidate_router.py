"""Step 1 candidate routing: takes structural regions (+ clause citations,
+ parsed CLIN rows) for one page and produces `ClassifiedCandidate`s tagged
with a canonical V3 category, a confidence, and explainable reason codes.

This is the layer that actually fixes the confirmed regressions
(docs/source-to-v3-mapping.md): TOC_ENTRY/heading regions never become
GENERAL_ACCEPTED_FIELD/CONTRACT_SUMMARY candidates in the first place, and
FORM_FIELD_LABEL -> FORM_FIELD_VALUE pairing requires same-page proximity
plus an identifier-compatible (non-prose) value before it is accepted.

Stops before persistence: callers get a list of `ClassifiedCandidate`
objects back and decide what to do with them. No V3 dataset table is
written to from this module.
"""

from __future__ import annotations

import re

from app.schemas.candidate_classification import ClassifiedCandidate, StructuralRegion
from app.services.clause_citation_scanner import ClauseCitation
from app.services.clin_block_detector import ParsedClinRow
from app.services.contract_summary_fields import (
    FIELD_KEY_TO_V3_COLUMN,
    is_plausible_business_label,
    match_label,
    validate_value,
)
from app.services.form_cell_associator import FormCellAssociation

_ATTACHMENT_KEYWORDS = ("attachment", "exhibit", "appendix")
_PERFORMANCE_KEYWORDS = (
    "period of performance",
    "place of performance",
    "delivery date",
    "delivery location",
    "fob",
    "commencement of work",
)
_FUNDING_KEYWORDS = (
    "acrn",
    "accounting classification",
    "appropriation",
    "obligated amount",
    "funds obligated",
    "line of accounting",
)

_FORM_LABEL_ITEM_RE = re.compile(r"^\d{1,2}[A-Za-z]?\.\s+(?P<label>.+)$")
_STOPWORDS = frozenset(
    "the a an of to in on for and or but is are was were be been being "
    "this that these those shall will would should may might must not "
    "whether if as by with from at it its their his her our your".split()
)

# Max vertical distance (points) for a FORM_FIELD_VALUE to be considered
# geometrically associated with a FORM_FIELD_LABEL on the same page.
_MAX_LABEL_VALUE_Y_DISTANCE = 20.0
# Max horizontal distance (points) between a label's left edge and a
# value's left edge for the SAME-ROW pairing to apply. Multi-column forms
# (e.g. SF33's "27. UNITED STATES OF AMERICA" / "28. AWARD DATE" sitting
# side by side on the same row-band) have multiple label/value pairs at
# the same y-position but different x - without this, the nearest-Y value
# in a *different* column gets picked instead of the correct same-column
# one (confirmed bug: "Esther Shannon", x0=20, matched "28. AWARD DATE",
# x0=527, over the correct "04/15/2025", x0=532, purely because it was
# closer in Y and came first in block order).
_MAX_LABEL_VALUE_X_DISTANCE = 250.0
# Fallback when bbox geometry is degenerate: value must appear within this
# many blocks of the label in reading order.
_MAX_LABEL_VALUE_BLOCK_GAP = 3
# When two-or-more semantically-valid value candidates for the same label
# are within this combined distance of each other, treat the pairing as
# genuinely ambiguous (-> QA_REVIEW, preserve both) rather than silently
# picking the marginally closer one.
_AMBIGUITY_DISTANCE_MARGIN = 15.0


def _looks_like_prose(text: str) -> bool:
    """Narrative protection (P0 spec section 8): identifier fields require
    identifier-compatible values, not sentence fragments."""

    words = text.split()
    if len(words) < 3:
        return False
    stopword_hits = sum(1 for w in words if w.lower().strip(",.;:") in _STOPWORDS)
    return stopword_hits >= 2 or len(words) > 10


def _is_degenerate_bbox(bbox: tuple[float, float, float, float] | None) -> bool:
    return bbox is None or bbox == (0.0, 0.0, 0.0, 0.0)


def _label_value_distance(
    label: StructuralRegion,
    value: StructuralRegion,
) -> float:
    """Lower is better. Combines vertical + horizontal offset so the
    closest candidate (not just the first one found in block order) wins
    when multiple values sit near a label."""

    label_mid_y = (label.bbox[1] + label.bbox[3]) / 2
    value_mid_y = (value.bbox[1] + value.bbox[3]) / 2
    y_distance = abs(label_mid_y - value_mid_y)
    x_distance = abs(label.bbox[0] - value.bbox[0])
    return y_distance + x_distance * 0.5


def _label_value_associated(
    label: StructuralRegion,
    value: StructuralRegion,
) -> tuple[bool, list[str]]:
    if label.page_number != value.page_number:
        return False, ["different_page"]

    # A value that precedes its label in extraction order is never the
    # right pairing on a standard form (labels precede their values) -
    # confirmed bug: a page-number stamp block appearing just before "5.
    # DATE ISSUED" in block order, and directly above it, was otherwise
    # geometrically plausible enough to be picked over the real value.
    if value.block_index < label.block_index:
        return False, ["value_precedes_label_in_reading_order"]

    if _is_degenerate_bbox(label.bbox) or _is_degenerate_bbox(value.bbox):
        gap = value.block_index - label.block_index
        if 0 < gap <= _MAX_LABEL_VALUE_BLOCK_GAP:
            return True, ["degenerate_geometry_block_adjacency"]
        return False, ["degenerate_geometry_not_adjacent"]

    label_mid_y = (label.bbox[1] + label.bbox[3]) / 2
    value_mid_y = (value.bbox[1] + value.bbox[3]) / 2
    y_close = abs(label_mid_y - value_mid_y) <= _MAX_LABEL_VALUE_Y_DISTANCE
    x_close = abs(label.bbox[0] - value.bbox[0]) <= _MAX_LABEL_VALUE_X_DISTANCE

    if y_close and x_close:
        return True, ["vertical_and_horizontal_proximity_same_field_column"]

    # Deliberately no block-index-adjacency fallback here: when real bbox
    # geometry is available but doesn't confirm alignment, trusting block
    # order alone produced confirmed wrong pairings (a page-number stamp,
    # a signature caption) over a real but geometrically-misaligned value.
    # Better to report no value (-> QA_REVIEW) than a wrong one - the
    # block-adjacency fallback is reserved for the degenerate-geometry
    # case above, where there is no bbox signal to trust instead.
    return False, ["no_geometric_proximity_in_same_column"]


def _clause_family_to_category(family: str, *, listing_context: bool | None) -> str:
    if family == "DFARS":
        # Per Step-1 instructions section 5: DFARS routes to the DFARS
        # dataset regardless of listing/narrative context (V3 has no
        # separate "DFARS incidental reference" sheet).
        return "DFARS"
    if listing_context:
        # FAR and GSAR both incorporate into Clauses when they appear in a
        # listing context (decision #2: GSAR uses Regulation="GSAR" in the
        # same Clauses dataset, not a new sheet).
        return "CLAUSE"
    # Narrative/incidental mention. V3's 14-category list has no
    # "GSAR_REFERENCE" bucket, so an incidental GSAR mention (none observed
    # in the regression contract - all its GSAR citations are in the
    # Section I listing) falls back to FAR_REFERENCE as the closest analog,
    # tagged with its real regulation in `regulation`. Flagged explicitly
    # here rather than silently assumed.
    return "FAR_REFERENCE"


def route_clause_citations(
    citations: list[ClauseCitation],
) -> list[ClassifiedCandidate]:
    candidates: list[ClassifiedCandidate] = []
    for citation in citations:
        category = _clause_family_to_category(
            citation.clause_family,
            listing_context=citation.listing_context,
        )
        reasons = [
            f"clause_family_{citation.clause_family.lower()}",
            f"classification_basis_{citation.classification_basis.lower()}",
        ]
        if citation.listing_context is True:
            reasons.append("listing_context_clause_citation_scanner")
            confidence = 0.88
        elif citation.listing_context is False:
            reasons.append("narrative_context_clause_citation_scanner")
            confidence = 0.8
        else:
            reasons.append("listing_context_unknown_no_regions_supplied")
            confidence = 0.6

        candidates.append(
            ClassifiedCandidate(
                category=category,  # type: ignore[arg-type]
                confidence=confidence,
                reason_codes=reasons,
                source_page=citation.page_number,
                evidence=citation.source_text,
                region_type="CLAUSE_LISTING" if citation.listing_context else "NARRATIVE",
                label=citation.clause_number,
                value=citation.title or None,
                regulation=citation.clause_family,  # type: ignore[arg-type]
                clause_number=citation.clause_number,
            )
        )
    return candidates


def _normalize_evidence_for_identity(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return collapsed[:80]


def deduplicate_clin_funding_overlap(
    candidates: list[ClassifiedCandidate],
) -> list[ClassifiedCandidate]:
    """Fixes a confirmed double-count: the same source line (e.g. "10301
    RD-541330-SB ... Obligated Amount: $0.00") gets found independently by
    the CLIN row parser (-> CLIN, correct) AND by the general block
    classifier, whose NARRATIVE keyword match on "obligated amount" also
    produces a competing FUNDING candidate for the identical text.

    Not a blanket "CLIN always wins" rule (a CLIN row may legitimately
    carry funding information that needs its own structured Funding
    record later) - this only collapses the case where the two
    candidates' evidence is the *same underlying source line* (matched by
    normalized page+text identity), keeping the CLIN candidate as primary
    and folding the funding-keyword signal into its reason codes instead
    of losing it or double-counting it.
    """

    by_identity: dict[tuple[int, str], list[ClassifiedCandidate]] = {}
    for candidate in candidates:
        key = (candidate.source_page, _normalize_evidence_for_identity(candidate.evidence))
        by_identity.setdefault(key, []).append(candidate)

    to_drop: set[int] = set()
    merged_reason_notes: dict[int, list[str]] = {}

    for group in by_identity.values():
        if len(group) < 2:
            continue
        clin_members = [c for c in group if c.category == "CLIN"]
        funding_members = [c for c in group if c.category == "FUNDING"]
        if not clin_members or not funding_members:
            continue
        primary = clin_members[0]
        for funding_candidate in funding_members:
            to_drop.add(id(funding_candidate))
            merged_reason_notes.setdefault(id(primary), []).append(
                "also_matched_funding_keyword_pattern_same_source_line"
            )

    deduplicated: list[ClassifiedCandidate] = []
    for candidate in candidates:
        if id(candidate) in to_drop:
            continue
        extra_notes = merged_reason_notes.get(id(candidate))
        if extra_notes:
            candidate = candidate.model_copy(
                update={"reason_codes": [*candidate.reason_codes, *extra_notes]}
            )
        deduplicated.append(candidate)

    return deduplicated


def route_clin_rows(rows: list[ParsedClinRow]) -> list[ClassifiedCandidate]:
    candidates: list[ClassifiedCandidate] = []
    for row in rows:
        reasons = list(row.reason_codes)
        if row.parent_line_item:
            reasons.append(f"slin_of_{row.parent_line_item}")
        candidates.append(
            ClassifiedCandidate(
                category="CLIN",
                confidence=row.confidence,
                reason_codes=reasons,
                source_page=row.page_number,
                evidence=row.source_text,
                region_type="TABLE_ROW",
                label=row.clin,
                value=row.amount,
            )
        )
    return candidates


def _split_embedded_colon_value(
    label: str, value: str | None
) -> tuple[str, str | None]:
    """"UEID: LLKXZRFEQMR3" as a single label must not become Normalized
    Field="UEID: LLKXZRFEQMR3" — the label is always cleaned to "UEID"
    when it has this shape, regardless of whether an independently-found
    `value` exists (keep that value if present; the colon-suffix is only
    used as a fallback value when nothing else was found)."""

    if ":" not in label:
        return label, value
    prefix, _, suffix = label.partition(":")
    prefix, suffix = prefix.strip(), suffix.strip()
    if prefix and suffix and len(suffix) <= 80:
        return prefix, (value if value else suffix)
    return label, value


_INSTRUCTION_VALUE_RE = re.compile(
    r"^\(?(see\b|the\b|enter\b|submit\b|check\b|this\b|if\b)", re.IGNORECASE
)


def _looks_like_real_value(value: str) -> bool:
    """A paired form-field VALUE must look like actual data, not a
    cross-reference or truncated instruction continuation. Confirmed bad
    pairings: a legitimate SF33 label ("Discount for Prompt Payment",
    "Acknowledgement of Amendments") paired with "(See Section I, Clause
    No. 52.232.8)" or "(The offeror acknowledges receipt of" — the LABEL
    is real, the VALUE is narrative, so label-vocabulary alone can't catch
    this; the value's own shape must be checked too."""

    stripped = value.strip()
    if not stripped:
        return False
    if _INSTRUCTION_VALUE_RE.match(stripped):
        return False
    if stripped.endswith(":"):
        # A "value" ending in a colon is itself a label fragment (e.g.
        # "UNITED STATES CODE AT:"), not real data.
        return False
    words = stripped.split()
    if len(words) >= 5:
        # A real form value (identifier, date, name, amount, short phrase)
        # is rarely 5+ words; that length is a narrative/cross-reference
        # fragment far more often than it's real data.
        return False
    return True


def route_form_cell_associations(
    associations: list[FormCellAssociation],
) -> list[ClassifiedCandidate]:
    """Routes Step 2 form-cell associations (line-granularity ownership)
    into ClassifiedCandidate rows. Prefer this path when LogicalLines are
    available; ``route_page_regions`` remains for block-level fallbacks.
    """

    candidates: list[ClassifiedCandidate] = []
    for cell in associations:
        label_bbox = (
            cell.label_line.x0,
            cell.label_line.y0,
            cell.label_line.x1,
            cell.label_line.y1,
        )
        value_bbox = (
            (
                cell.value_line.x0,
                cell.value_line.y0,
                cell.value_line.x1,
                cell.value_line.y1,
            )
            if cell.value_line is not None
            else label_bbox
        )

        if cell.association == "ambiguous":
            candidates.append(
                ClassifiedCandidate(
                    category="QA_REVIEW",
                    confidence=cell.confidence,
                    reason_codes=[
                        *cell.reason_codes,
                        f"alternates: {', '.join(repr(v) for v in cell.alternate_values)}",
                    ],
                    source_page=cell.page_number,
                    evidence=cell.label_text,
                    region_type="FORM_FIELD_LABEL",
                    label=cell.label_text,
                    value=None,
                    bbox=label_bbox,
                    extraction_method=cell.label_line.extraction_method,
                )
            )
            continue

        if cell.value_text is None:
            candidates.append(
                ClassifiedCandidate(
                    category="QA_REVIEW",
                    confidence=cell.confidence,
                    reason_codes=list(cell.reason_codes),
                    source_page=cell.page_number,
                    evidence=cell.label_text,
                    region_type="FORM_FIELD_LABEL",
                    label=cell.label_text,
                    value=None,
                    bbox=label_bbox,
                    extraction_method=cell.label_line.extraction_method,
                )
            )
            continue

        field_key = cell.field_key
        clean_label, clean_value = _split_embedded_colon_value(
            cell.label_text, cell.value_text
        )

        reasons = ["form_cell_association"]
        if field_key and field_key in FIELD_KEY_TO_V3_COLUMN:
            category = "CONTRACT_SUMMARY"
            reasons.append(f"field_key_{field_key}")
        elif field_key:
            category = "GENERAL_ACCEPTED_FIELD"
            reasons.append(f"field_key_{field_key}")
        elif is_plausible_business_label(clean_label) and (
            clean_value is None or _looks_like_real_value(clean_value)
        ):
            # Quality-gate follow-up: no recognized vocabulary, but the
            # label shape (multi-word, not a structural/navigational
            # phrase, not prose-length) is plausibly a real business
            # datum, AND the value itself looks like data rather than a
            # cross-reference/instruction continuation — accepted, but
            # distinguishable in reason_codes from a vocabulary-matched
            # field.
            category = "GENERAL_ACCEPTED_FIELD"
            reasons.append("no_recognized_field_vocabulary_but_plausible_label")
        else:
            # Single common word or structural/navigational phrase (e.g.
            # "FOR", "NAME", "SIGNATURE", "TABLE OF CONTENTS") — never a
            # business field, regardless of a geometrically-plausible
            # value pairing. Routed to NOISE, which never reaches V3 All
            # Fields (all_fields_builder only accepts GENERAL_ACCEPTED_FIELD).
            category = "NOISE"
            reasons.append("label_not_plausible_business_field")

        candidates.append(
            ClassifiedCandidate(
                category=category,  # type: ignore[arg-type]
                confidence=cell.confidence,
                reason_codes=[*reasons, *cell.reason_codes],
                source_page=cell.page_number,
                evidence=f"{cell.label_text} -> {cell.value_text}",
                region_type="FORM_FIELD_VALUE",
                label=clean_label,
                value=clean_value,
                bbox=value_bbox,
                extraction_method=(
                    cell.value_line.extraction_method
                    if cell.value_line is not None
                    else cell.label_line.extraction_method
                ),
            )
        )
    return candidates


def route_page_regions(
    regions: list[StructuralRegion],
) -> list[ClassifiedCandidate]:
    """Routes non-clause, non-CLIN structural regions (headings, TOC lines,
    footers, form fields, narrative) to their V3 category."""

    candidates: list[ClassifiedCandidate] = []

    label_regions = [r for r in regions if r.region_type == "FORM_FIELD_LABEL"]
    value_regions = [r for r in regions if r.region_type == "FORM_FIELD_VALUE"]
    claimed_value_indices: set[int] = set()

    for label in label_regions:
        match = _FORM_LABEL_ITEM_RE.match(label.text)
        label_text = match.group("label") if match else label.text
        field_key = match_label(label_text)

        # Every geometrically-plausible, non-prose value candidate for this
        # label, closest first - not just the single nearest one, so
        # semantic validation and ambiguity detection have something to
        # choose between.
        scored: list[tuple[float, StructuralRegion, list[str]]] = []
        for value in value_regions:
            if value.block_index in claimed_value_indices:
                continue
            associated, reasons = _label_value_associated(label, value)
            if not associated:
                continue
            if _looks_like_prose(value.text):
                # Narrative protection: reject prose-shaped values outright,
                # even if geometrically adjacent - do not pair, do not mark
                # Passed.
                continue
            distance = (
                _label_value_distance(label, value)
                if not _is_degenerate_bbox(label.bbox)
                and not _is_degenerate_bbox(value.bbox)
                else value.block_index - label.block_index
            )
            scored.append((distance, value, reasons))
        scored.sort(key=lambda item: item[0])

        if field_key is not None:
            # Field-specific semantic validation: only a value that
            # actually looks like the kind of thing this label asks for is
            # eligible - this is what stops a solicitation-number-shaped
            # string from being accepted as "Date Issued" purely because
            # it was the nearest available candidate.
            validated = []
            rejected_reasons: list[str] = []
            for distance, value, reasons in scored:
                result = validate_value(field_key, value.text)
                if result.is_valid:
                    validated.append((distance, value, reasons, result.reason))
                else:
                    rejected_reasons.append(f"{value.text!r}:{result.reason}")

            if not validated:
                candidates.append(
                    ClassifiedCandidate(
                        category="QA_REVIEW",
                        confidence=0.35,
                        reason_codes=[
                            "form_field_label_no_semantically_valid_value_nearby",
                            f"field_key_{field_key}",
                            *rejected_reasons[:3],
                        ],
                        source_page=label.page_number,
                        evidence=label.text,
                        region_type=label.region_type,
                        label=label_text,
                        value=None,
                        bbox=label.bbox,
                        extraction_method=label.extraction_method,
                    )
                )
                continue

            if len(validated) >= 2 and (validated[1][0] - validated[0][0]) < _AMBIGUITY_DISTANCE_MARGIN:
                # Two (or more) candidates are both plausible and nearly
                # equidistant - guessing here is exactly what produced the
                # confirmed wrong pairings. Report both, don't pick.
                top_two = ", ".join(f"{v.text!r}" for _, v, _, _ in validated[:2])
                candidates.append(
                    ClassifiedCandidate(
                        category="QA_REVIEW",
                        confidence=0.5,
                        reason_codes=[
                            "ambiguous_multiple_validated_candidates",
                            f"field_key_{field_key}",
                            f"candidates: {top_two}",
                        ],
                        source_page=label.page_number,
                        evidence=label.text,
                        region_type=label.region_type,
                        label=label_text,
                        value=None,
                        bbox=label.bbox,
                        extraction_method=label.extraction_method,
                    )
                )
                continue

            distance, best_value, best_reasons, validation_reason = validated[0]
            claimed_value_indices.add(best_value.block_index)
            category = (
                "CONTRACT_SUMMARY" if field_key in FIELD_KEY_TO_V3_COLUMN else "GENERAL_ACCEPTED_FIELD"
            )
            candidates.append(
                ClassifiedCandidate(
                    category=category,  # type: ignore[arg-type]
                    confidence=min(label.confidence, best_value.confidence) + 0.15,
                    reason_codes=[
                        "form_field_label_value_pair",
                        f"field_key_{field_key}",
                        "semantic_validation_passed",
                        validation_reason,
                        *best_reasons,
                    ],
                    source_page=label.page_number,
                    evidence=f"{label.text} -> {best_value.text}",
                    region_type="FORM_FIELD_VALUE",
                    label=label_text,
                    value=best_value.text,
                    bbox=best_value.bbox,
                    extraction_method=best_value.extraction_method,
                )
            )
            continue

        # No recognized field vocabulary for this label: keep the prior,
        # simpler behavior (closest geometric match) - still requires a
        # non-empty, non-prose candidate to exist at all.
        if not scored:
            candidates.append(
                ClassifiedCandidate(
                    category="QA_REVIEW",
                    confidence=0.4,
                    reason_codes=["form_field_label_no_identifier_shaped_value_nearby"],
                    source_page=label.page_number,
                    evidence=label.text,
                    region_type=label.region_type,
                    label=label_text,
                    value=None,
                    bbox=label.bbox,
                    extraction_method=label.extraction_method,
                )
            )
            continue

        distance, best_value, best_reasons = scored[0]
        claimed_value_indices.add(best_value.block_index)
        candidates.append(
            ClassifiedCandidate(
                category="GENERAL_ACCEPTED_FIELD",
                confidence=min(label.confidence, best_value.confidence) + 0.1,
                reason_codes=["form_field_label_value_pair", "no_recognized_field_vocabulary", *best_reasons],
                source_page=label.page_number,
                evidence=f"{label.text} -> {best_value.text}",
                region_type="FORM_FIELD_VALUE",
                label=label_text,
                value=best_value.text,
                bbox=best_value.bbox,
                extraction_method=best_value.extraction_method,
            )
        )

    for region in regions:
        if region.region_type in ("FORM_FIELD_LABEL", "FORM_FIELD_VALUE"):
            continue

        text_lower = region.text.lower()

        if region.region_type in ("TOC_ENTRY", "SECTION_HEADING", "SUBSECTION_HEADING"):
            candidates.append(
                ClassifiedCandidate(
                    category="STRUCTURAL_HEADING",
                    confidence=region.confidence,
                    reason_codes=[*region.reason_codes, "structural_heading_never_a_field"],
                    source_page=region.page_number,
                    evidence=region.text,
                    region_type=region.region_type,
                    bbox=region.bbox,
                    extraction_method=region.extraction_method,
                )
            )

        elif region.region_type == "FOOTER_HEADER":
            candidates.append(
                ClassifiedCandidate(
                    category="NOISE",
                    confidence=region.confidence,
                    reason_codes=[*region.reason_codes, "page_furniture"],
                    source_page=region.page_number,
                    evidence=region.text,
                    region_type=region.region_type,
                    bbox=region.bbox,
                    extraction_method=region.extraction_method,
                )
            )

        elif region.region_type == "TABLE_HEADER":
            candidates.append(
                ClassifiedCandidate(
                    category="NOISE",
                    confidence=region.confidence,
                    reason_codes=[*region.reason_codes, "table_scaffolding_not_a_value"],
                    source_page=region.page_number,
                    evidence=region.text,
                    region_type=region.region_type,
                    bbox=region.bbox,
                    extraction_method=region.extraction_method,
                )
            )

        elif region.region_type == "TABLE_ROW":
            # CLIN-shaped table rows are already handled via
            # route_clin_rows (parsed with column semantics). A generic
            # table row that isn't CLIN-shaped is still an accepted
            # structured value, routed conservatively.
            if any(k in text_lower for k in _FUNDING_KEYWORDS):
                category = "FUNDING"
            else:
                category = "GENERAL_ACCEPTED_FIELD"
            candidates.append(
                ClassifiedCandidate(
                    category=category,  # type: ignore[arg-type]
                    confidence=region.confidence - 0.1,
                    reason_codes=[*region.reason_codes, "generic_table_row"],
                    source_page=region.page_number,
                    evidence=region.text,
                    region_type=region.region_type,
                    bbox=region.bbox,
                    extraction_method=region.extraction_method,
                )
            )

        elif region.region_type == "NARRATIVE":
            if any(k in text_lower for k in _ATTACHMENT_KEYWORDS):
                candidates.append(
                    ClassifiedCandidate(
                        category="ATTACHMENT",
                        confidence=0.55,
                        reason_codes=["narrative_attachment_keyword", "needs_downstream_extraction"],
                        source_page=region.page_number,
                        evidence=region.text,
                        region_type=region.region_type,
                        bbox=region.bbox,
                        extraction_method=region.extraction_method,
                    )
                )
            elif any(k in text_lower for k in _PERFORMANCE_KEYWORDS):
                candidates.append(
                    ClassifiedCandidate(
                        category="PERFORMANCE_DELIVERY",
                        confidence=0.55,
                        reason_codes=["narrative_performance_keyword", "needs_downstream_extraction"],
                        source_page=region.page_number,
                        evidence=region.text,
                        region_type=region.region_type,
                        bbox=region.bbox,
                        extraction_method=region.extraction_method,
                    )
                )
            elif any(k in text_lower for k in _FUNDING_KEYWORDS):
                candidates.append(
                    ClassifiedCandidate(
                        category="FUNDING",
                        confidence=0.55,
                        reason_codes=["narrative_funding_keyword", "needs_downstream_extraction"],
                        source_page=region.page_number,
                        evidence=region.text,
                        region_type=region.region_type,
                        bbox=region.bbox,
                        extraction_method=region.extraction_method,
                    )
                )
            else:
                candidates.append(
                    ClassifiedCandidate(
                        category="NARRATIVE",
                        confidence=region.confidence,
                        reason_codes=region.reason_codes,
                        source_page=region.page_number,
                        evidence=region.text,
                        region_type=region.region_type,
                        bbox=region.bbox,
                        extraction_method=region.extraction_method,
                    )
                )

        else:  # OTHER
            candidates.append(
                ClassifiedCandidate(
                    category="NOISE",
                    confidence=region.confidence,
                    reason_codes=[*region.reason_codes, "unclassified_low_confidence"],
                    source_page=region.page_number,
                    evidence=region.text,
                    region_type=region.region_type,
                    bbox=region.bbox,
                    extraction_method=region.extraction_method,
                )
            )

    return candidates
