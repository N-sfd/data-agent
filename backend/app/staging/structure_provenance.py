"""CellProvenance builders for staging adapters that interpret the
schema-neutral source structure (app/source_structure/). Shared so every
structure-consuming profile (generic, invoice, …) points a cell at its
evidence in exactly the same way."""

from __future__ import annotations

from app.models.document import Document
from app.source_structure.models import (
    FieldCandidate,
    StructuredRegion,
    TableCandidate,
    TableCell,
)
from app.staging.models import CellProvenance, SourceColumn
from app.staging.provenance import make_provenance


def _source_type(extraction_method: str):
    return "html" if extraction_method == "dom" else None


def _ocr_gate(provenance: CellProvenance, extraction_method: str, confidence, contested: bool = False) -> None:
    """OCR-read structure values carry the lowest confidence of their words
    and whether the OCR passes disagreed on them; the validator then
    requires known, high confidence and agreement before Verified. Native
    PDF text and HTML DOM values are never gated."""

    if extraction_method == "ocr":
        provenance.ocr_gate = True
        provenance.ocr_confidence = float(confidence) if confidence is not None else None
        provenance.ocr_contested = bool(contested)


def field_provenance(document: Document, candidate: FieldCandidate) -> CellProvenance:
    """Provenance of a label/value candidate's VALUE. A single-line value is
    highlighted as text inside its box; a multi-line one (an address) as
    its whole region."""

    provenance = make_provenance(
        document,
        page=candidate.page,
        evidence=candidate.evidence_text,
        bbox=candidate.value_bbox,
        extraction_method=f"{candidate.extraction_method}:{candidate.structural_relation}",
        region_id=candidate.source_region_ids[0] if candidate.source_region_ids else candidate.candidate_id,
        anchor=candidate.raw_label.strip(),
        locator=candidate.source_locator,
        source_type=_source_type(candidate.extraction_method),
    )
    single_line = "\n" not in candidate.raw_value.strip()
    provenance.highlight_text = candidate.raw_value.strip() if single_line else None
    _ocr_gate(provenance, candidate.extraction_method, candidate.ocr_confidence, candidate.ocr_contested)
    return provenance


def table_cell_provenance(
    document: Document,
    table: TableCandidate,
    row: list[TableCell],
    cell: TableCell,
    anchor: str | None,
) -> CellProvenance:
    row_text = " | ".join(c.text for c in row if c.text)
    provenance = make_provenance(
        document,
        page=table.page,
        evidence=row_text,
        bbox=cell.bbox,
        extraction_method=f"{table.extraction_method}:{table.detection_method}",
        region_id=cell.region_id,
        anchor=anchor,
        locator=cell.source_locator,
        source_type=_source_type(table.extraction_method),
    )
    provenance.highlight_text = cell.text or None
    _ocr_gate(provenance, table.extraction_method, cell.ocr_confidence, cell.ocr_contested)
    return provenance


def region_provenance(
    document: Document,
    region: StructuredRegion,
    *,
    highlight: str | None = None,
    kind: str | None = None,
) -> CellProvenance:
    provenance = make_provenance(
        document,
        page=region.page,
        evidence=region.text,
        bbox=region.bbox,
        extraction_method=f"{region.extraction_method}:{kind or region.region_type.lower()}",
        region_id=region.region_id,
        anchor=region.text.splitlines()[0] if region.text else None,
        locator=region.source_locator,
        source_type=_source_type(region.extraction_method),
    )
    provenance.highlight_text = highlight
    _ocr_gate(
        provenance,
        region.extraction_method,
        region.structural_metadata.get("ocr_confidence"),
        bool(region.structural_metadata.get("ocr_contested")),
    )
    return provenance


def source_column(table: TableCandidate, column_index: int) -> SourceColumn:
    roles = list(table.column_hints.get(column_index, []))
    has_header = bool(table.header_cells)
    return SourceColumn(
        raw_header=table.headers[column_index] if has_header and column_index < len(table.headers) else None,
        column_index=column_index,
        structural_role=roles[0] if roles else None,
        structural_roles=roles,
    )
