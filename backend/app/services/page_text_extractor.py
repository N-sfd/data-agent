from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
import time

import fitz

from app.core.config import Settings
from app.core.observability import log_event
from app.services.ocr_detection import (
    OCRDetection,
    detect_ocr_requirement,
)


def _run_with_timeout(fn, timeout_seconds: float):
    """Run a native (non-interruptible) call with a wall-clock bound.

    MuPDF's OCR is a direct C call — it has no timeout parameter of its
    own, so a hang there (e.g. a broken tessdata path some builds treat
    as a slow retry loop instead of a fast failure) would otherwise block
    the calling thread forever. A timed-out call's thread is abandoned
    (Python cannot forcibly kill it), but the caller recovers immediately
    instead of hanging the whole request.
    """

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    finally:
        # wait=False: on timeout, don't block here waiting for a hung
        # native call to finish — let the orphaned thread run its course.
        executor.shutdown(wait=False)


# Ceiling on the long side of an OCR raster, independent of page size or
# DPI metadata. A page's point-dimensions can be wrong or absent (a
# multi-frame TIFF with no resolution tag, a malformed PDF, ...); without
# this, get_textpage_ocr()/get_pixmap() render at settings.ocr_dpi against
# whatever the page claims its size is, and an oversized page can allocate
# a raster large enough to OOM the process. 4200px covers Letter (3300px),
# A4 (3508px), and Legal (4200px) at a full 300 DPI with zero clamping —
# every real-world scan renders at its intended quality — while still
# bounding peak memory for anything larger or for pages whose reported
# size can't be trusted (missing/garbage DPI, malformed dimensions).
MAX_OCR_RASTER_DIMENSION_PX = 4200


def _bounded_ocr_dpi(page: fitz.Page, requested_dpi: int) -> int:
    long_side_pt = max(page.rect.width, page.rect.height)
    if long_side_pt <= 0:
        return requested_dpi
    max_dpi_for_cap = MAX_OCR_RASTER_DIMENSION_PX * 72.0 / long_side_pt
    return max(1, min(requested_dpi, int(max_dpi_for_cap)))


@dataclass(frozen=True)
class TextBlockData:
    block_index: int
    block_type: str
    text: str

    x0: float
    y0: float
    x1: float
    y1: float

    extraction_method: str


@dataclass(frozen=True)
class PageExtractionData:
    page_number: int
    page_label: str | None

    page_width: float
    page_height: float

    native_text: str
    ocr_text: str | None
    final_text: str

    extraction_method: str

    detection: OCRDetection

    ocr_attempted: bool
    ocr_succeeded: bool
    ocr_error: str | None

    blocks: list[TextBlockData]


def convert_blocks(
    raw_blocks: list[tuple],
    *,
    extraction_method: str,
) -> list[TextBlockData]:
    converted: list[TextBlockData] = []

    for block_index, block in enumerate(raw_blocks):
        if len(block) < 7:
            continue

        x0, y0, x1, y1, text, _, block_type = block[:7]

        text_value = str(text).strip()

        if not text_value:
            continue

        readable_block_type = (
            "text" if block_type == 0 else "image"
        )

        converted.append(
            TextBlockData(
                block_index=block_index,
                block_type=readable_block_type,
                text=text_value,
                x0=float(x0),
                y0=float(y0),
                x1=float(x1),
                y1=float(y1),
                extraction_method=extraction_method,
            )
        )

    return converted


def get_page_label(
    document: fitz.Document,
    page_number: int,
) -> str | None:
    try:
        labels = document.get_page_labels()

        if not labels:
            return None

        return document[page_number - 1].get_label() or None

    except Exception:
        return None


def extract_page(
    *,
    document: fitz.Document,
    page_index: int,
    settings: Settings,
    run_ocr: bool,
    force_ocr: bool = False,
) -> PageExtractionData:
    page = document.load_page(page_index)
    page_number = page_index + 1

    native_text = page.get_text(
        "text",
        sort=True,
    ).strip()

    native_blocks = page.get_text(
        "blocks",
        sort=True,
    )

    detection = detect_ocr_requirement(
        page=page,
        native_text=native_text,
        native_blocks=native_blocks,
        settings=settings,
    )

    log_event(
        "ocr_detection",
        stage="rendering_ocr",
        page=page_number,
        requires_ocr=detection.requires_ocr,
        force_ocr=force_ocr,
        native_chars=len(native_text),
        image_count=detection.image_count,
        reasons=detection.reasons[:5],
    )

    native_block_data = convert_blocks(
        native_blocks,
        extraction_method="native",
    )

    ocr_text: str | None = None
    ocr_attempted = False
    ocr_succeeded = False
    ocr_error: str | None = None

    final_text = native_text
    final_blocks = native_block_data
    extraction_method = "native"

    should_run_ocr = (
        run_ocr
        and settings.ocr_enabled
        and (force_ocr or detection.requires_ocr)
    )

    if should_run_ocr:
        ocr_attempted = True
        mupdf_started = time.perf_counter()

        try:
            tessdata = (
                str(settings.tessdata_path)
                if settings.tessdata_path
                else None
            )

            effective_dpi = _bounded_ocr_dpi(
                page, settings.ocr_dpi
            )

            if effective_dpi != settings.ocr_dpi:
                log_event(
                    "ocr_dpi_clamped",
                    stage="rendering_ocr",
                    page=page_number,
                    requested_dpi=settings.ocr_dpi,
                    effective_dpi=effective_dpi,
                    page_width_pt=page.rect.width,
                    page_height_pt=page.rect.height,
                )

            ocr_text_page = _run_with_timeout(
                lambda: page.get_textpage_ocr(
                    language=settings.ocr_language,
                    dpi=effective_dpi,
                    full=True,
                    tessdata=tessdata,
                ),
                settings.ocr_page_timeout_seconds,
            )

            ocr_text = page.get_text(
                "text",
                textpage=ocr_text_page,
                sort=True,
            ).strip()

            ocr_blocks = page.get_text(
                "blocks",
                textpage=ocr_text_page,
                sort=True,
            )

            ocr_block_data = convert_blocks(
                ocr_blocks,
                extraction_method="ocr",
            )

            prefer_ocr = force_ocr or len(ocr_text) > len(native_text)

            if prefer_ocr and ocr_text:
                final_text = ocr_text
                final_blocks = ocr_block_data
                extraction_method = "ocr"
                ocr_succeeded = True

            elif ocr_text:
                final_text = native_text
                final_blocks = native_block_data
                extraction_method = "native"
                ocr_succeeded = True

            log_event(
                "ocr_mupdf",
                stage="rendering_ocr",
                status="ok" if ocr_text else "empty",
                page=page_number,
                ocr_engine="mupdf_tesseract",
                duration_ms=int((time.perf_counter() - mupdf_started) * 1000),
                text_chars=len(ocr_text or ""),
                tessdata_set=bool(tessdata),
            )

        except FutureTimeoutError:
            ocr_error = (
                f"MuPDF OCR exceeded {settings.ocr_page_timeout_seconds}s "
                "and was abandoned."
            )
            log_event(
                "ocr_mupdf",
                stage="rendering_ocr",
                status="timeout",
                error_category="Timeout",
                page=page_number,
                ocr_engine="mupdf_tesseract",
                duration_ms=int((time.perf_counter() - mupdf_started) * 1000),
                timeout_seconds=settings.ocr_page_timeout_seconds,
            )
        except Exception as exc:
            ocr_error = str(exc)
            log_event(
                "ocr_mupdf",
                stage="rendering_ocr",
                status="error",
                error_category=type(exc).__name__,
                page=page_number,
                ocr_engine="mupdf_tesseract",
                duration_ms=int((time.perf_counter() - mupdf_started) * 1000),
            )

        # Raster / scanned pages: if MuPDF OCR yielded nothing, try
        # pytesseract directly against a rendered pixmap.
        if (force_ocr or not final_text.strip()) and not (
            ocr_text and ocr_text.strip()
        ):
            try:
                from app.services.embedded_image_ocr import ocr_image_bytes

                pixmap = page.get_pixmap(
                    dpi=_bounded_ocr_dpi(page, settings.ocr_dpi)
                )
                fallback = ocr_image_bytes(
                    pixmap.tobytes("png"),
                    language=settings.ocr_language,
                    timeout_seconds=settings.ocr_page_timeout_seconds,
                    page_number=page_number,
                )
                if fallback:
                    ocr_text = fallback
                    final_text = fallback
                    final_blocks = [
                        TextBlockData(
                            block_index=0,
                            block_type="text",
                            text=fallback,
                            x0=0.0,
                            y0=0.0,
                            x1=float(page.rect.width),
                            y1=float(page.rect.height),
                            extraction_method="ocr",
                        )
                    ]
                    extraction_method = "ocr"
                    ocr_succeeded = True
                    ocr_error = None
            except Exception as exc:
                if ocr_error is None:
                    ocr_error = str(exc)

        if ocr_attempted and not (final_text or "").strip():
            if ocr_error is None:
                ocr_error = "OCR executed but produced no extractable text."
            ocr_succeeded = False
            log_event(
                "ocr_empty_result",
                stage="rendering_ocr",
                status="warning",
                page=page_number,
                force_ocr=force_ocr,
                requires_ocr=detection.requires_ocr,
                error_type=ocr_error[:120],
            )

    log_event(
        "page_text_extracted",
        stage="rendering_ocr",
        page=page_number,
        extraction_method=extraction_method,
        ocr_attempted=ocr_attempted,
        ocr_succeeded=ocr_succeeded,
        page_text_chars=len(final_text or ""),
        has_ocr_error=bool(ocr_error),
    )

    return PageExtractionData(
        page_number=page_number,
        page_label=get_page_label(
            document,
            page_number,
        ),
        page_width=float(page.rect.width),
        page_height=float(page.rect.height),
        native_text=native_text,
        ocr_text=ocr_text,
        final_text=final_text,
        extraction_method=extraction_method,
        detection=detection,
        ocr_attempted=ocr_attempted,
        ocr_succeeded=ocr_succeeded,
        ocr_error=ocr_error,
        blocks=final_blocks,
    )
