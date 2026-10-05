"""Two-column pages (a sidebar beside the main column) are read column by
column; tables crossing the gap and single-column text never split."""

from __future__ import annotations

from app.source_structure.pdf_structure import Word, column_gutter, extract_page_structure


def line(text: str, x: float, y: float, size: float = 11.0) -> list[Word]:
    words, cursor = [], x
    for token in text.split():
        width = 5.5 * len(token)
        words.append(Word(token, cursor, y, cursor + width, y + size, size))
        cursor += width + 3
    return words


def sidebar_page() -> list[Word]:
    words: list[Word] = []
    # Sidebar: short labelled lines, not aligned with the main column.
    for i in range(12):
        words += line("Event Management daily work", 20, 306 + i * 21)
    # Main column: running text every 14pt.
    for i in range(30):
        words += line("Organized and managed all areas of events for the school", 260, 100 + i * 14)
    return words


def test_a_sidebar_layout_splits_at_the_gutter():
    gutter = column_gutter(sidebar_page())
    assert gutter is not None and 150 < gutter < 260


def test_a_table_crossing_the_gap_does_not_split():
    words: list[Word] = []
    for i in range(30):
        y = 100 + i * 14
        words += line("Benchtop meter with probe and stand", 40, y)
        words += line("2 EA 685.00 1,370.00", 380, y)
    assert column_gutter(words) is None


def test_single_column_text_does_not_split():
    words: list[Word] = []
    for i in range(30):
        words += line("A professional with an experience of eight years with proven skills", 40, 100 + i * 14)
    assert column_gutter(words) is None


def test_columns_never_share_a_line():
    structure = extract_page_structure(page_number=1, words=sidebar_page(), extraction_method="native")
    columns = {region.structural_metadata.get("column") for region in structure.regions}
    assert columns == {"left", "right"}
    for region in structure.regions:
        # No text line joins sidebar words with main-column words.
        assert not ("Management" in region.text and "Organized" in region.text)


def test_scanned_pages_are_never_split():
    """OCR baselines drift with skew, so a scanned table could pass for two
    columns: column reading applies to native text only."""

    structure = extract_page_structure(page_number=1, words=sidebar_page(), extraction_method="ocr")
    assert {region.structural_metadata.get("column") for region in structure.regions} == {None}
