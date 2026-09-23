"""Step 1: structural region detection + canonical candidate routing.

This is a read-only classification layer. It never persists anything and
never calls an LLM on its normal path (deterministic, geometry/text driven).
Its job is to sit between raw page extraction and the (not-yet-built) V3
dataset extractors, so that Table-of-Contents lines, section headings, and
narrative prose never reach a canonical dataset as if they were field
values - the confirmed root cause of the pre-V3 "All Fields" contamination.
"""

from typing import Literal

from pydantic import BaseModel, Field

StructuralRegionType = Literal[
    "FORM_FIELD_LABEL",
    "FORM_FIELD_VALUE",
    "TABLE_HEADER",
    "TABLE_ROW",
    "SECTION_HEADING",
    "SUBSECTION_HEADING",
    "TOC_ENTRY",
    "CLAUSE_LISTING",
    "NARRATIVE",
    "FOOTER_HEADER",
    "OTHER",
]

V3Category = Literal[
    "CONTRACT_SUMMARY",
    "CLIN",
    "FUNDING",
    "PERFORMANCE_DELIVERY",
    "ATTACHMENT",
    "CLAUSE",
    "FAR_REFERENCE",
    "DFARS",
    "GENERAL_ACCEPTED_FIELD",
    "SOURCE_DOCUMENT_METADATA",
    "QA_REVIEW",
    "STRUCTURAL_HEADING",
    "NARRATIVE",
    "NOISE",
]


class StructuralRegion(BaseModel):
    """One page block, tagged with what kind of document structure it is."""

    page_number: int
    block_index: int
    region_type: StructuralRegionType
    text: str
    bbox: tuple[float, float, float, float] | None = None
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)
    extraction_method: str = "native"


class ClassifiedCandidate(BaseModel):
    """A structural region (or a sub-span of one, e.g. a clause citation)
    routed to a canonical V3 category, with an explainable result."""

    category: V3Category
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)
    source_page: int
    evidence: str
    region_type: StructuralRegionType
    label: str | None = None
    value: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    extraction_method: str = "native"

    # Populated only for CLAUSE/DFARS/FAR_REFERENCE candidates.
    regulation: Literal["FAR", "DFARS", "GSAR"] | None = None
    clause_number: str | None = None
