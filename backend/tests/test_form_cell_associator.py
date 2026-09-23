"""Step 2 form-cell association fixtures — multiple layouts, no hardcoding
of the regression contract's values beyond shape checks."""

from __future__ import annotations

import fitz

from app.services.form_cell_associator import associate_form_cells
from app.services.line_model import LogicalLine, lines_from_fitz_page


def _line(
    text: str,
    *,
    x0: float,
    y0: float,
    x1: float | None = None,
    y1: float | None = None,
    page: int = 1,
    index: int = 0,
) -> LogicalLine:
    return LogicalLine(
        page_number=page,
        parent_block_index=0,
        line_index=index,
        text=text,
        x0=x0,
        y0=y0,
        x1=x1 if x1 is not None else x0 + 120.0,
        y1=y1 if y1 is not None else y0 + 10.0,
        extraction_method="native",
        source="native_dict_span",
    )


def test_label_above_value_same_column() -> None:
    lines = [
        _line("2. CONTRACT NUMBER", x0=20.0, y0=40.0, index=0),
        _line("47QRCA25DSF07", x0=21.0, y0=52.0, index=1),
    ]
    cells = associate_form_cells(lines=lines)
    assert len(cells) == 1
    assert cells[0].field_key == "contract_number"
    assert cells[0].value_text == "47QRCA25DSF07"
    assert cells[0].association == "below_label"


def test_two_column_form_independent_ownership() -> None:
    lines = [
        _line("2. CONTRACT NUMBER", x0=20.0, y0=40.0, index=0),
        _line("3. SOLICITATION NUMBER", x0=200.0, y0=40.0, index=1),
        _line("47QRCA25DSF07", x0=21.0, y0=52.0, index=2),
        _line("47QRCA23R0001", x0=201.0, y0=52.0, index=3),
    ]
    cells = associate_form_cells(lines=lines)
    by_key = {c.field_key: c for c in cells}
    assert by_key["contract_number"].value_text == "47QRCA25DSF07"
    assert by_key["solicitation_number"].value_text == "47QRCA23R0001"
    # Each value claimed once — no cross-column reuse.
    assert by_key["contract_number"].value_text != by_key["solicitation_number"].value_text


def test_label_left_of_value() -> None:
    lines = [
        _line("5. DATE ISSUED", x0=20.0, y0=80.0, x1=140.0, y1=90.0, index=0),
        _line("02/03/2025", x0=160.0, y0=80.0, x1=230.0, y1=90.0, index=1),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells[0].field_key == "date_issued"
    assert cells[0].value_text == "02/03/2025"
    assert cells[0].association == "right_of_label"


def test_empty_field_stays_unassociated() -> None:
    lines = [
        _line("6. REQUISITION/PURCHASE NUMBER", x0=20.0, y0=100.0, index=0),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells[0].value_text is None
    assert cells[0].association == "unassociated"


def test_value_without_confident_label_is_not_auto_owned() -> None:
    lines = [
        _line("47QRCA25DSF07", x0=20.0, y0=50.0, index=0),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells == []


def test_wrong_shaped_neighbor_rejected_for_date_field() -> None:
    lines = [
        _line("5. DATE ISSUED", x0=20.0, y0=40.0, index=0),
        _line("47QRCA23R0001", x0=21.0, y0=52.0, index=1),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells[0].value_text is None
    assert cells[0].association == "unassociated"
    assert any("does_not_parse_as_date" in r for r in cells[0].reason_codes)


def test_ambiguous_two_identifiers_below_label() -> None:
    lines = [
        _line("2. CONTRACT NUMBER", x0=20.0, y0=40.0, index=0),
        _line("47QRCA25DSF07", x0=21.0, y0=50.0, index=1),
        _line("47QRCA23R0001", x0=22.0, y0=55.0, index=2),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells[0].association == "ambiguous"
    assert cells[0].value_text is None
    assert len(cells[0].alternate_values) >= 2


def test_multiline_value_takes_first_valid_line_only() -> None:
    # Ownership is per line; multi-line freeform values need a later
    # continuation pass. For identifier fields, only the first valid line
    # is claimed.
    lines = [
        _line("2. CONTRACT NUMBER", x0=20.0, y0=40.0, index=0),
        _line("47QRCA25DSF07", x0=21.0, y0=52.0, index=1),
        _line("continued address line", x0=21.0, y0=64.0, index=2),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells[0].value_text == "47QRCA25DSF07"


def test_synthetic_fitz_two_column_layout() -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((19, 50), "2. CONTRACT NUMBER", fontsize=8)
    page.insert_text((202, 50), "3. SOLICITATION NUMBER", fontsize=8)
    page.insert_text((19, 62), "47QRCA25DSF07", fontsize=8)
    page.insert_text((202, 62), "47QRCA23R0001", fontsize=8)
    lines = lines_from_fitz_page(page=page, page_number=1)
    cells = associate_form_cells(lines=lines)
    by_key = {c.field_key: c for c in cells if c.field_key}
    assert by_key["contract_number"].value_text == "47QRCA25DSF07"
    assert by_key["solicitation_number"].value_text == "47QRCA23R0001"


def test_same_line_colon_separated_label_value() -> None:
    lines = [
        _line("Award Date: 04/15/2025", x0=20.0, y0=40.0, x1=220.0, index=0),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells[0].field_key == "award_date"
    assert cells[0].value_text == "04/15/2025"
    assert cells[0].association == "same_line"


def test_multipart_telephone_under_label_composes() -> None:
    """SF33 packs AREA CODE + NUMBER as separate spans under TELEPHONE."""

    lines = [
        _line("B. TELEPHONE (NO COLLECT CALLS)", x0=317.0, y0=224.0, x1=414.0, index=0),
        _line("AREA CODE", x0=280.0, y0=233.0, x1=311.0, index=1),
        _line("NUMBER", x0=330.0, y0=233.0, x1=353.0, index=2),
        _line("240", x0=294.0, y0=242.0, x1=311.0, index=3),
        _line("541-1679", x0=341.0, y0=242.0, x1=386.0, index=4),
    ]
    cells = associate_form_cells(lines=lines)
    phone = next(c for c in cells if c.field_key == "telephone")
    assert phone.value_text == "240-541-1679"
    assert "composed_multipart_phone" in phone.reason_codes


def test_toc_letter_section_is_not_form_label() -> None:
    """TOC 'B. SUPPLIES...' must not own the next heading as a field value."""

    lines = [
        _line("B. SUPPLIES OR SERVICES AND PRICES/COSTS", x0=20.0, y0=40.0, x1=280.0, index=0),
        _line("1 CONUS Standardized Labor Categories", x0=21.0, y0=52.0, index=1),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells == []


def test_numbered_prose_list_item_is_not_form_label() -> None:
    lines = [
        _line(
            "3. OCO-directed non-standard custom or specialized labor categories that are",
            x0=20.0,
            y0=40.0,
            x1=400.0,
            index=0,
        ),
        _line("B.8.1 CONUS Standardized Labor Categories", x0=21.0, y0=52.0, index=1),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells == []


def test_ocr_equivalent_label_above_value() -> None:
    lines = [
        LogicalLine(
            page_number=1,
            parent_block_index=0,
            line_index=0,
            text="2. CONTRACT NUMBER",
            x0=20.0,
            y0=40.0,
            x1=140.0,
            y1=50.0,
            extraction_method="ocr",
            source="ocr_word_layer",
            confidence=0.92,
        ),
        LogicalLine(
            page_number=1,
            parent_block_index=0,
            line_index=1,
            text="47QRCA25DSF07",
            x0=21.0,
            y0=52.0,
            x1=120.0,
            y1=62.0,
            extraction_method="ocr",
            source="ocr_word_layer",
            confidence=0.91,
        ),
    ]
    cells = associate_form_cells(lines=lines)
    assert cells[0].field_key == "contract_number"
    assert cells[0].value_text == "47QRCA25DSF07"
