from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProcessedPage:
    page_number: int
    text: str
    tables_detected: int = 0


@dataclass
class ProcessedDocument:
    document_id: str
    file_type: str
    page_count: int
    has_native_text: bool
    ocr_pages: list[int] = field(default_factory=list)
    pages: list[ProcessedPage] = field(default_factory=list)


class FileProcessor:
    """Common interface for PDF, DOCX, and image ingestion."""

    kind: str

    def process(self, **kwargs) -> dict:
        raise NotImplementedError
