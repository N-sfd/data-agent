from dataclasses import dataclass

import fitz

from app.core.config import Settings


@dataclass(frozen=True)
class OCRDetection:
    requires_ocr: bool
    reasons: list[str]

    character_count: int
    word_count: int
    text_block_count: int
    image_count: int

    text_coverage_ratio: float
    image_coverage_ratio: float


def rectangle_area(rectangle: fitz.Rect) -> float:
    width = max(0.0, rectangle.x1 - rectangle.x0)
    height = max(0.0, rectangle.y1 - rectangle.y0)

    return width * height


def calculate_text_coverage(
    page: fitz.Page,
    text_blocks: list[tuple],
) -> float:
    page_area = rectangle_area(page.rect)

    if page_area <= 0:
        return 0.0

    total_text_area = 0.0

    for block in text_blocks:
        if len(block) < 7:
            continue

        x0, y0, x1, y1, text, _, block_type = block[:7]

        if block_type != 0:
            continue

        if not str(text).strip():
            continue

        block_rect = fitz.Rect(x0, y0, x1, y1)
        total_text_area += rectangle_area(block_rect)

    return min(total_text_area / page_area, 1.0)


def calculate_image_coverage(page: fitz.Page) -> tuple[int, float]:
    page_area = rectangle_area(page.rect)

    if page_area <= 0:
        return 0, 0.0

    image_rectangles: list[fitz.Rect] = []

    for image_info in page.get_image_info():
        bbox = image_info.get("bbox")

        if not bbox:
            continue

        image_rectangles.append(fitz.Rect(bbox))

    image_area = sum(
        rectangle_area(rectangle)
        for rectangle in image_rectangles
    )

    return (
        len(image_rectangles),
        min(image_area / page_area, 1.0),
    )


def suspicious_glyph_ratio(text: str) -> float:
    """Share of characters that look like broken OCR / ToUnicode garbage."""

    if not text:
        return 0.0

    bad = 0
    for char in text:
        code = ord(char)
        if char in {"\ufffd", "\u0000"}:
            bad += 1
        elif code < 32 and char not in {"\n", "\r", "\t"}:
            bad += 1
        # Private Use Area often appears in broken embedded fonts.
        elif 0xE000 <= code <= 0xF8FF:
            bad += 1

    return bad / max(len(text), 1)


def detect_ocr_requirement(
    page: fitz.Page,
    native_text: str,
    native_blocks: list[tuple],
    settings: Settings,
) -> OCRDetection:
    stripped_text = native_text.strip()

    character_count = len(stripped_text)
    word_count = len(stripped_text.split())

    text_block_count = sum(
        1
        for block in native_blocks
        if len(block) >= 7
        and block[6] == 0
        and str(block[4]).strip()
    )

    text_coverage_ratio = calculate_text_coverage(
        page,
        native_blocks,
    )

    image_count, image_coverage_ratio = calculate_image_coverage(
        page
    )

    glyph_ratio = suspicious_glyph_ratio(stripped_text)

    reasons: list[str] = []

    if character_count < settings.ocr_min_character_count:
        reasons.append(
            "Native text contains too few characters."
        )

    if word_count < settings.ocr_min_word_count:
        reasons.append(
            "Native text contains too few words."
        )

    if text_coverage_ratio < settings.ocr_min_text_coverage:
        reasons.append(
            "Extracted text covers very little of the page."
        )

    if glyph_ratio > settings.ocr_max_bad_glyph_ratio:
        reasons.append(
            "Native text contains a high ratio of suspicious glyphs."
        )

    if (
        image_count > 0
        and image_coverage_ratio
        >= settings.ocr_max_image_ratio
        and character_count
        < settings.ocr_min_character_count * 4
    ):
        reasons.append(
            "A large image covers most of the page while "
            "little native text is available."
        )

    blank_page = (
        character_count == 0
        and image_count == 0
    )

    if blank_page:
        reasons = [
            "The page appears blank."
        ]

    requires_ocr = bool(reasons) and not blank_page

    return OCRDetection(
        requires_ocr=requires_ocr,
        reasons=reasons,
        character_count=character_count,
        word_count=word_count,
        text_block_count=text_block_count,
        image_count=image_count,
        text_coverage_ratio=text_coverage_ratio,
        image_coverage_ratio=image_coverage_ratio,
    )
