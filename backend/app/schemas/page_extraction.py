from datetime import datetime

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class ExtractedTextBlock(BaseModel):
    block_index: int
    block_type: str
    text: str
    bounding_box: BoundingBox
    extraction_method: str


class OCRDetectionResult(BaseModel):
    requires_ocr: bool
    reasons: list[str]

    character_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    text_block_count: int = Field(ge=0)
    image_count: int = Field(ge=0)

    text_coverage_ratio: float = Field(ge=0)
    image_coverage_ratio: float = Field(ge=0)


class ExtractedPageResponse(BaseModel):
    page_number: int
    page_label: str | None

    page_width: float
    page_height: float

    extraction_method: str

    native_text: str
    ocr_text: str | None
    final_text: str

    character_count: int
    word_count: int
    text_block_count: int
    image_count: int

    text_coverage_ratio: float
    image_coverage_ratio: float

    requires_ocr: bool
    ocr_attempted: bool
    ocr_succeeded: bool
    ocr_error: str | None

    blocks: list[ExtractedTextBlock] = Field(
        default_factory=list
    )


class DocumentExtractionRequest(BaseModel):
    run_ocr: bool = True

    page_start: int | None = Field(
        default=None,
        ge=1,
    )

    page_end: int | None = Field(
        default=None,
        ge=1,
    )

    force_reprocess: bool = False


class DocumentExtractionProgress(BaseModel):
    document_id: str
    status: str

    page_current: int
    page_total: int
    percent: int

    native_pages: int
    ocr_pages: int
    ocr_completed_pages: int


class DocumentExtractionSummary(BaseModel):
    document_id: str
    status: str

    total_document_pages: int
    pages_requested: int
    pages_processed: int

    native_pages: int
    ocr_required_pages: int
    ocr_completed_pages: int
    failed_pages: int

    page_numbers_processed: list[int]
    warnings: list[str]

    completed_at: datetime


class StoredPageResponse(BaseModel):
    document_id: str
    page_number: int
    page_label: str | None

    extraction_method: str
    final_text: str

    requires_ocr: bool
    ocr_attempted: bool
    ocr_succeeded: bool

    character_count: int
    word_count: int

    page_width: float
    page_height: float

    source_reference: str


class StoredBlockResponse(BaseModel):
    block_index: int
    block_type: str
    text: str

    x0: float
    y0: float
    x1: float
    y1: float

    extraction_method: str
    source_reference: str


class PageRenderResponse(BaseModel):
    page_number: int
    image_data_url: str

    page_width: float
    page_height: float

    highlight: BoundingBox | None = None
