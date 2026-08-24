from pathlib import Path

from app.core.errors import UNSUPPORTED_FILE_TYPE
from app.services.document_extraction import DocumentExtractionError
from app.services.file_processors.docx_processor import DocxProcessor
from app.services.file_processors.image_processor import ImageProcessor
from app.services.file_processors.pdf_processor import PdfProcessor

_PROCESSORS = {
    ".pdf": PdfProcessor(),
    ".docx": DocxProcessor(),
    ".png": ImageProcessor(),
    ".jpg": ImageProcessor(),
    ".jpeg": ImageProcessor(),
}


def get_processor(file_path: Path):
    processor = _PROCESSORS.get(file_path.suffix.lower())

    if processor is None:
        raise DocumentExtractionError(
            "This file type is not supported. "
            "Upload a PDF, DOCX, PNG, or JPG.",
            code=UNSUPPORTED_FILE_TYPE,
        )

    return processor
