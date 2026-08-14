from dataclasses import dataclass

import fitz

from app.core.config import Settings
from app.services.ocr_detection import (
    OCRDetection,
    detect_ocr_requirement,
)


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
        and detection.requires_ocr
    )

    if should_run_ocr:
        ocr_attempted = True

        try:
            tessdata = (
                str(settings.tessdata_path)
                if settings.tessdata_path
                else None
            )

            ocr_text_page = page.get_textpage_ocr(
                language=settings.ocr_language,
                dpi=settings.ocr_dpi,
                full=True,
                tessdata=tessdata,
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

            if len(ocr_text) > len(native_text):
                final_text = ocr_text
                final_blocks = ocr_block_data
                extraction_method = "ocr"
                ocr_succeeded = bool(ocr_text)

            elif ocr_text:
                final_text = native_text
                final_blocks = native_block_data
                extraction_method = "native"
                ocr_succeeded = True

        except Exception as exc:
            ocr_error = str(exc)

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
