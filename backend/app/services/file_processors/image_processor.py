from io import BytesIO
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import PAGE_EXTRACTION_FAILED
from app.models.document import Document
from app.services.document_extraction import (
    DocumentExtractionError,
    process_fitz_pages,
)
from app.services.file_processors.base import FileProcessor
from app.services.security_validation import RASTER_EXTENSIONS


def _split_multiframe_tiff(file_path: Path) -> Path | None:
    """Multi-frame TIFFs (fax/scanner output) hold one page per frame, but
    MuPDF only ever exposes the first. Rebuild one PDF page per frame so
    the rest of the pipeline (per-page OCR, DocumentPage rows) sees every
    frame. Returns None for single-frame TIFFs — caller keeps the original.
    """

    from PIL import Image, ImageSequence
    import fitz

    with Image.open(file_path) as image:
        frame_count = getattr(image, "n_frames", 1)
        if frame_count <= 1:
            return None

        synthetic = fitz.open()
        for frame in ImageSequence.Iterator(image):
            rgb = frame.convert("RGB")
            buffer = BytesIO()
            rgb.save(buffer, format="PNG")
            width, height = rgb.size
            page = synthetic.new_page(width=width, height=height)
            page.insert_image(page.rect, stream=buffer.getvalue())

    synthetic_path = file_path.with_suffix(".frames.pdf")
    synthetic.save(synthetic_path)
    synthetic.close()
    return synthetic_path


def _ensure_fitz_readable(file_path: Path) -> Path:
    """Normalize BMP/WEBP (and odd rasters) to PNG when needed."""

    suffix = file_path.suffix.lower()

    if suffix in {".tif", ".tiff"}:
        split = _split_multiframe_tiff(file_path)
        if split is not None:
            return split
        return file_path

    if suffix in {".png", ".jpg", ".jpeg"}:
        return file_path

    try:
        import fitz

        with fitz.open(file_path) as probe:
            if probe.page_count >= 1:
                return file_path
    except Exception:
        pass

    from PIL import Image

    normalized = file_path.with_suffix(".png")
    with Image.open(file_path) as image:
        image.convert("RGB").save(normalized, format="PNG")
    return normalized


class ImageProcessor(FileProcessor):
    kind = "image"

    def process(
        self,
        *,
        database: Session,
        document_record: Document,
        file_path: Path,
        settings: Settings,
        run_ocr: bool,
        page_start: int | None,
        page_end: int | None,
        force_reprocess: bool,
        started_at: float,
    ) -> dict:
        if not file_path.exists():
            raise DocumentExtractionError(
                "The stored image could not be found.",
                code=PAGE_EXTRACTION_FAILED,
            )

        if file_path.suffix.lower() not in RASTER_EXTENSIONS:
            raise DocumentExtractionError(
                "Unsupported image type.",
                code=PAGE_EXTRACTION_FAILED,
            )

        readable = _ensure_fitz_readable(file_path)

        return process_fitz_pages(
            database=database,
            document_record=document_record,
            file_path=readable,
            settings=settings,
            run_ocr=run_ocr,
            page_start=page_start,
            page_end=page_end,
            force_reprocess=force_reprocess,
            started_at=started_at,
            is_raster_image=True,
        )
