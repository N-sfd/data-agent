from types import SimpleNamespace

from app.services.clin_block_detector import (
    detect_repeated_records,
    parse_clin_rows,
    parse_clin_rows_from_tables,
    parse_clin_rows_from_text,
)


def _page(
    number: int,
    *,
    text: str = "",
    tables: list[dict] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        page_number=number,
        final_text=text,
        tables_json=tables,
    )


def test_detect_repeated_records_still_matches_four_digit_clins() -> None:
    # Existing behavior (live caller: schema_discovery.py) must not regress.
    page = _page(
        4,
        tables=[
            {
                "headers": ["CLIN", "Description"],
                "rows": [["0001", "Base"], ["0002", "Option 1"]],
            }
        ],
    )
    blocks = detect_repeated_records(page=page)
    assert len(blocks) == 1
    assert blocks[0].row_count == 2


def test_detect_repeated_records_matches_five_digit_domain_clins() -> None:
    # The regression contract's GSA OASIS+ CLINs are 5 digits (10300,
    # 10301, ...), not the 4-digit DoD-style shape the pattern used to
    # require exclusively.
    page = _page(
        3,
        tables=[
            {
                "headers": [],
                "rows": [["10300", "Domain"], ["10301", "RD-541330-SB"]],
            }
        ],
    )
    blocks = detect_repeated_records(page=page)
    assert len(blocks) == 1


def test_parse_clin_rows_from_tables_maps_headers_to_fields() -> None:
    page = _page(
        4,
        tables=[
            {
                "headers": ["CLIN", "Description", "Qty", "Unit", "Unit Price", "Amount"],
                "rows": [
                    ["0001", "Base Period - SB-DBMACC", "600000000", "Each", "1", "600000000"],
                ],
            }
        ],
    )
    rows = parse_clin_rows_from_tables(page=page)
    assert len(rows) == 1
    row = rows[0]
    assert row.clin == "0001"
    assert row.description == "Base Period - SB-DBMACC"
    assert row.quantity == "600000000"
    assert row.amount == "600000000"


def test_parse_clin_rows_from_text_fallback_no_table_structure() -> None:
    text = (
        "10300   RD0003 - Research and Development                    0.00\n"
        "10301   RD-541330-SB                                         0.00\n"
        "        541330 Engineering Services\n"
        "10302   RD-541330E1-SB                                       0.00\n"
    )
    page = _page(3, text=text, tables=None)
    rows = parse_clin_rows_from_text(page=page)
    clins = {row.clin for row in rows}
    assert clins == {"10300", "10301", "10302"}
    assert all(row.amount == "0.00" for row in rows)


def test_parse_clin_rows_prefers_table_structure_over_text_fallback() -> None:
    page = _page(
        4,
        text="0001   Base Period                                  600000000.00",
        tables=[
            {
                "headers": ["CLIN", "Description", "Amount"],
                "rows": [["0001", "Base Period", "600000000"]],
            }
        ],
    )
    rows = parse_clin_rows(page=page)
    assert len(rows) == 1
    assert rows[0].confidence == 0.85  # table-path confidence, not text-path


def test_slin_detected_as_child_of_prior_numeric_clin() -> None:
    page = _page(
        4,
        tables=[
            {
                "headers": ["CLIN", "Description"],
                "rows": [
                    ["0001", "Base"],
                    ["0001AA", "Base SLIN A"],
                ],
            }
        ],
    )
    rows = parse_clin_rows_from_tables(page=page)
    slin_row = next(r for r in rows if r.clin == "0001AA")
    assert slin_row.parent_line_item == "0001"
    assert slin_row.relationship == "SLIN"

    parent_row = next(r for r in rows if r.clin == "0001")
    assert parent_row.parent_line_item is None


def test_sequential_domain_clins_are_not_fabricated_into_a_hierarchy() -> None:
    # 10300/10301 are sequential but NOT a SLIN-suffix relationship - Step 1
    # must not invent a parent/child link from digit similarity alone.
    page = _page(
        3,
        tables=[
            {
                "headers": [],
                "rows": [["10300", "Domain"], ["10301", "RD-541330-SB"]],
            }
        ],
    )
    rows = parse_clin_rows_from_tables(page=page)
    assert all(r.parent_line_item is None for r in rows)
