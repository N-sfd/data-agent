"""Canonical V3 document — the single source of truth for Results UI, CSV,
and Complete Excel (docs/v3-schema-manifest.md). Every field name mirrors
the ground-truth workbook's own column headers exactly, so callers never
need a name-mapping step to build an export.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RowProvenance(BaseModel):
    """Internal provenance the staging workbook adapter needs (row identity,
    PDF-point bbox, extraction method). Excluded from serialization so the
    /v3 JSON and the V3 CSV/XLSX exports are unchanged."""

    row_id: str
    bbox: list[float] | None = None
    # "pdf_points" or "ocr_pixels" (see app/services/evidence_geometry.py).
    bbox_space: str = "pdf_points"
    extraction_method: str | None = None


class AllFieldsRow(BaseModel):
    category: str
    normalized_field: str
    value: str
    source_file: str
    source_page: int
    evidence: str
    extraction_method: str
    qa_status: str
    row_provenance: RowProvenance | None = Field(default=None, exclude=True)


class ClinRow(BaseModel):
    clin: str
    option_base: str | None = None
    description: str | None = None
    pricing_type: str | None = None
    max_quantity: str | None = None
    unit: str | None = None
    unit_price: float | None = None
    max_amount: float | None = None
    status: str | None = None
    fob: str | None = None
    purchase_request: str | None = None
    psc: str | None = None
    pop_start: str | None = None
    pop_end: str | None = None
    ship_to: str | None = None
    dodaac: str | None = None
    source_page: int | None = None
    evidence: str | None = None
    qa_status: str | None = None
    row_provenance: RowProvenance | None = Field(default=None, exclude=True)


class FundingRow(BaseModel):
    funding_level: str | None = None
    clin: str | None = None
    funding_status: str | None = None
    amount: float | None = None
    accounting_appropriation: str | None = None
    purchase_request: str | None = None
    source_page: int | None = None
    evidence: str | None = None
    qa_status: str | None = None
    row_provenance: RowProvenance | None = Field(default=None, exclude=True)


class PerformanceDeliveryRow(BaseModel):
    record_type: str | None = None
    clin: str | None = None
    start: str | None = None
    end_timing: str | None = None
    location_destination: str | None = None
    requirement: str | None = None
    source_page: int | None = None
    evidence: str | None = None
    qa_status: str | None = None
    row_provenance: RowProvenance | None = Field(default=None, exclude=True)


class AttachmentRow(BaseModel):
    attachment_reference: str
    title_description: str | None = None
    included_in_portfolio: str | None = None
    source_page: int | None = None
    evidence: str | None = None
    qa_status: str | None = None
    row_provenance: RowProvenance | None = Field(default=None, exclude=True)


class ClauseRow(BaseModel):
    regulation: str
    clause_number: str
    clause_title: str | None = None
    alternate_deviation: str | None = None
    effective_date: str | None = None
    incorporation_type: str | None = None
    source_page: int | None = None
    evidence: str | None = None
    qa_status: str | None = None
    row_provenance: RowProvenance | None = Field(default=None, exclude=True)


class FarReferenceRow(BaseModel):
    far_reference: str
    reference_type: str | None = None
    subject_context: str | None = None
    source_page: int | None = None
    evidence: str | None = None
    contract_clause: str | None = None
    qa_status: str | None = None
    row_provenance: RowProvenance | None = Field(default=None, exclude=True)


class SourceDocumentRow(BaseModel):
    source_document: str
    role: str
    pages: int
    extraction_status: str


class QaReviewRow(BaseModel):
    qa_check: str
    result: str
    details: str
    action: str


class ContractSummaryRow(BaseModel):
    contract_number: str | None = None
    solicitation_rfp: str | None = None
    contract_vehicle: str | None = None
    agency_office: str | None = None
    contractor: str | None = None
    award_date: str | None = None
    ceiling_max_aggregate: str | None = None
    minimum_guarantee: str | None = None
    base_period: str | None = None
    options: str | None = None
    max_duration: str | None = None
    task_order_range: str | None = None
    naics: str | None = None
    size_standard: str | None = None
    source_file: str | None = None
    source_page: int | None = None
    evidence: str | None = None
    qa_status: str | None = None
    # Per-column {page, evidence, confidence, bbox, extraction_method},
    # keyed by V3 column header. Internal only — never exported.
    field_provenance: dict[str, dict] = Field(default_factory=dict, exclude=True)


class ExtractionOutcome(BaseModel):
    """See app/services/extraction_outcome.py for the status vocabulary."""

    status: str
    title: str
    message: str
    details: list[str] = []
    record_count: int = 0
    needs_review_count: int = 0


class NormalizedV3Document(BaseModel):
    document_id: str
    document_filename: str
    all_fields: list[AllFieldsRow]
    clins: list[ClinRow]
    funding: list[FundingRow]
    performance_delivery: list[PerformanceDeliveryRow]
    attachments: list[AttachmentRow]
    clauses: list[ClauseRow]
    far_references: list[FarReferenceRow]
    dfars: list[ClauseRow]
    source_documents: list[SourceDocumentRow]
    qa_review: list[QaReviewRow]
    contract_summary: ContractSummaryRow | None
    # Filled in by v3_reader after the datasets are assembled; None only
    # while that assembly is in progress.
    extraction_outcome: ExtractionOutcome | None = None
