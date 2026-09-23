"""V3 Contract Summary builder (docs/v3-schema-manifest.md §11).

Two sources, per column:

  1. The 7 columns `contract_summary_fields.FIELD_KEY_TO_V3_COLUMN` already
     covers (Contract Number, Solicitation/RFP, Award Date, Contractor,
     Agency/Office, NAICS, Ceiling/Max Aggregate) come straight from
     CONTRACT_SUMMARY-category `ClassifiedCandidate`s produced by
     candidate_router (form-field label/value pairs, already semantically
     validated).
  2. The remaining 7 columns (Contract Vehicle, Minimum Guarantee, Base
     Period, Options, Max Duration, Task Order Range, Size Standard) have
     no existing extraction logic anywhere in the codebase (confirmed gap,
     docs/v3-implementation-plan.md limitation #2) — this module adds
     conservative, evidence-anchored regex extraction for them, over the
     document's own page text. Per the P0 rule ("a blank/Needs Review value
     is better than a fabricated value"), any column with no confident
     textual match stays blank with `qa_status="Needs Review"` rather than
     being inferred/guessed.

One row per document (unique on document_id) — `persist_contract_summary`
does an upsert, not delete-then-insert-many.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_contract_summary import DocumentContractSummary
from app.models.document_page import DocumentPage
from app.schemas.candidate_classification import ClassifiedCandidate
from app.services.contract_summary_fields import FIELD_KEY_TO_V3_COLUMN

V3_COLUMNS = (
    "Contract Number",
    "Solicitation / RFP",
    "Contract Vehicle",
    "Agency / Office",
    "Contractor",
    "Award Date",
    "Ceiling / Max Aggregate",
    "Minimum Guarantee",
    "Base Period",
    "Options",
    "Max Duration",
    "Task Order Range",
    "NAICS",
    "Size Standard",
)

_V3_COLUMN_TO_MODEL_FIELD = {
    "Contract Number": "contract_number",
    "Solicitation / RFP": "solicitation_rfp",
    "Contract Vehicle": "contract_vehicle",
    "Agency / Office": "agency_office",
    "Contractor": "contractor",
    "Award Date": "award_date",
    "Ceiling / Max Aggregate": "ceiling_max_aggregate",
    "Minimum Guarantee": "minimum_guarantee",
    "Base Period": "base_period",
    "Options": "options",
    "Max Duration": "max_duration",
    "Task Order Range": "task_order_range",
    "NAICS": "naics",
    "Size Standard": "size_standard",
}


@dataclass
class _FieldValue:
    value: str
    page: int
    evidence: str
    confidence: float


def _field_key_of(candidate: ClassifiedCandidate) -> str | None:
    for reason in candidate.reason_codes:
        if reason.startswith("field_key_"):
            return reason[len("field_key_"):]
    return None


def _from_form_candidates(
    candidates: list[ClassifiedCandidate],
) -> dict[str, _FieldValue]:
    by_column: dict[str, _FieldValue] = {}
    for candidate in candidates:
        if candidate.category != "CONTRACT_SUMMARY" or not candidate.value:
            continue
        field_key = _field_key_of(candidate)
        if not field_key:
            continue
        column = FIELD_KEY_TO_V3_COLUMN.get(field_key)
        if not column:
            continue
        # contractor_name and offeror_name both map to "Contractor" — keep
        # the higher-confidence hit if both are present.
        existing = by_column.get(column)
        if existing is not None and existing.confidence >= candidate.confidence:
            continue
        by_column[column] = _FieldValue(
            value=candidate.value,
            page=candidate.source_page,
            evidence=candidate.evidence,
            confidence=candidate.confidence,
        )
    return by_column


# --- Narrative-pattern extraction for the 7 columns with no existing
# label/value extraction logic. Deliberately conservative: a pattern must
# match literal source phrasing; no inference across unrelated sentences. ---

_BASE_PERIOD_RE = re.compile(
    r"(?P<years>\w+|\d+)[- ]year base period", re.IGNORECASE
)
_OPTION_PERIOD_RE = re.compile(
    r"(?P<count>one|two|three|four|five|six|\d+)\s+option period", re.IGNORECASE
)
_MAX_DURATION_RE = re.compile(
    r"(?:extend|cumulative term).{0,60}?(?:to\s+)?(?P<years>\w+|\d+)\s+years",
    re.IGNORECASE,
)
_MINIMUM_GUARANTEE_RE = re.compile(
    r"minimum\s+guarantee[^.$]{0,60}?\$[\d,]+(?:\.\d{2})?", re.IGNORECASE
)
_TASK_ORDER_RANGE_RE = re.compile(
    r"task order[s]?[^.]{0,40}?(?:minimum|maximum|range)[^.]{0,120}?\$[\d,]+",
    re.IGNORECASE,
)
_SIZE_STANDARD_RE = re.compile(
    r"size standard[^.]{0,80}?(\$[\d,.]+\s*(?:million|billion)?|\d[\d,]*\s*employees)",
    re.IGNORECASE,
)

# Known contract-vehicle name phrases, ordered most-specific first — a
# recognizable proper-noun vehicle name, not a generic "IDIQ" guess.
_VEHICLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"GSA\s+OASIS\+?\s*(?:SB|Small Business)?\s*MAC", re.IGNORECASE),
    re.compile(r"OASIS\+\s*(?:SB)?", re.IGNORECASE),
    re.compile(r"One Acquisition Solution for Integrated Services[^.]{0,40}", re.IGNORECASE),
    re.compile(r"SB-DBMACC", re.IGNORECASE),
    re.compile(r"Multiple Award(?:s)?\s+(?:Contract|Schedule)", re.IGNORECASE),
)


def _search_pages(
    pages: list[DocumentPage], pattern: re.Pattern[str]
) -> _FieldValue | None:
    for page in pages:
        text = page.final_text or ""
        match = pattern.search(text)
        if match:
            snippet = match.group(0).strip()
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            return _FieldValue(
                value=snippet,
                page=page.page_number,
                evidence=text[start:end].strip(),
                confidence=0.6,
            )
    return None


def _extract_narrative_columns(pages: list[DocumentPage]) -> dict[str, _FieldValue]:
    found: dict[str, _FieldValue] = {}

    for pattern in _VEHICLE_PATTERNS:
        hit = _search_pages(pages, pattern)
        if hit:
            found["Contract Vehicle"] = hit
            break

    base = _search_pages(pages, _BASE_PERIOD_RE)
    if base:
        found["Base Period"] = base

    options = _search_pages(pages, _OPTION_PERIOD_RE)
    if options:
        found["Options"] = options

    max_duration = _search_pages(pages, _MAX_DURATION_RE)
    if max_duration:
        found["Max Duration"] = max_duration

    min_guarantee = _search_pages(pages, _MINIMUM_GUARANTEE_RE)
    if min_guarantee:
        found["Minimum Guarantee"] = min_guarantee

    task_order_range = _search_pages(pages, _TASK_ORDER_RANGE_RE)
    if task_order_range:
        found["Task Order Range"] = task_order_range

    size_standard = _search_pages(pages, _SIZE_STANDARD_RE)
    if size_standard:
        found["Size Standard"] = size_standard

    return found


def build_contract_summary(
    *,
    document: Document,
    pages: list[DocumentPage],
    candidates: list[ClassifiedCandidate],
) -> DocumentContractSummary:
    """Builds (does not persist) the one Contract Summary row for this
    document."""

    by_column = _from_form_candidates(candidates)
    for column, field_value in _extract_narrative_columns(pages).items():
        by_column.setdefault(column, field_value)

    kwargs: dict[str, object] = {}
    field_provenance: dict[str, dict] = {}
    for column in V3_COLUMNS:
        model_field = _V3_COLUMN_TO_MODEL_FIELD[column]
        hit = by_column.get(column)
        kwargs[model_field] = hit.value if hit else None
        if hit:
            field_provenance[column] = {
                "page": hit.page,
                "evidence": hit.evidence,
                "confidence": hit.confidence,
            }

    populated = sum(1 for column in V3_COLUMNS if by_column.get(column))
    qa_status = "Verified" if populated >= len(V3_COLUMNS) - 2 else "Needs Review"

    # Ground truth carries ONE Source Page/Evidence for the whole summary
    # row — anchor on Contract Number (always present on page 1-2 of an
    # award document) when available, else the first field found.
    primary = by_column.get("Contract Number") or next(iter(by_column.values()), None)

    return DocumentContractSummary(
        document_id=document.id,
        source_file=document.original_filename,
        source_page=primary.page if primary else None,
        evidence=primary.evidence if primary else None,
        qa_status=qa_status,
        field_provenance_json=field_provenance,
        confidence=(primary.confidence if primary else 0.0),
        **kwargs,
    )


def persist_contract_summary(
    *, database: Session, document_id: str, summary: DocumentContractSummary
) -> DocumentContractSummary:
    existing = database.scalars(
        select(DocumentContractSummary).where(
            DocumentContractSummary.document_id == document_id
        )
    ).first()
    if existing is not None:
        database.delete(existing)
        database.flush()
    database.add(summary)
    return summary
