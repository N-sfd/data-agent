from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NormalizedPage:
    """Common page model produced by every DocumentAdapter."""

    page: int
    text: str
    images: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    width: float = 612.0
    height: float = 792.0
    native_text_available: bool = True
    ocr_used: bool = False


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
    """Adapter interface: native first, OCR only when needed downstream."""

    kind: str

    def can_handle(self, mime_type: str, extension: str) -> bool:
        return False

    def process(self, **kwargs) -> dict:
        raise NotImplementedError
