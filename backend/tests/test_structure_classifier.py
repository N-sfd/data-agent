from app.services.page_text_extractor import TextBlockData
from app.services.structure_classifier import (
    DocumentContext,
    build_document_context,
    classify_page_regions,
)


def _block(
    index: int,
    text: str,
    *,
    x0: float = 72.0,
    y0: float = 100.0,
    x1: float = 400.0,
    y1: float = 112.0,
    extraction_method: str = "native",
) -> TextBlockData:
    return TextBlockData(
        block_index=index,
        block_type="text",
        text=text,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        extraction_method=extraction_method,
    )


def test_toc_line_with_dot_leaders_is_toc_entry() -> None:
    blocks = [
        _block(0, "B.8 LABOR CATEGORIES ......................................11"),
    ]
    regions = classify_page_regions(
        page_number=6, blocks=blocks, tables=None, page_height=792.0
    )
    assert regions[0].region_type == "TOC_ENTRY"


def test_toc_dense_page_catches_subsection_fragment_without_pagenum() -> None:
    # Simulates the confirmed regression: "B.8.1 CONUS Standardized Labor
    # Categories" split across block boundaries such that the trailing page
    # number ends up in a different block than the heading text.
    toc_blocks = [
        _block(0, "B.6 TASK ORDER CONTRACT TYPES..........................11"),
        _block(1, "B.7 TASK ORDER PRICING (ALL ORDER TYPES) ..............11"),
        _block(2, "B.8 LABOR CATEGORIES ...................................11"),
        _block(3, "B.8.1 CONUS Standardized Labor Categories"),  # no pagenum tail
    ]
    context = build_document_context(pages=[(6, toc_blocks, 792.0)])
    assert 6 in context.toc_pages

    regions = classify_page_regions(
        page_number=6,
        blocks=toc_blocks,
        tables=None,
        page_height=792.0,
        doc_context=context,
    )
    fragment = next(r for r in regions if r.text.startswith("B.8.1"))
    assert fragment.region_type == "TOC_ENTRY"
    assert "toc_context_page_density" in fragment.reason_codes


def test_naics_codes_toc_fragment_is_toc_entry_not_field() -> None:
    toc_blocks = [
        _block(0, "C.2.1 Management and Advisory Domain ...................18"),
        _block(
            1,
            "C.2.1.1 Management and Advisory Domain NAICS Codes..............18",
        ),
        _block(2, "C.2.2 Technical and Engineering Domain..................19"),
        _block(3, "C.2.2.1 Technical and Engineering Domain NAICS Codes............19"),
    ]
    context = build_document_context(pages=[(6, toc_blocks, 792.0)])
    regions = classify_page_regions(
        page_number=6,
        blocks=toc_blocks,
        tables=None,
        page_height=792.0,
        doc_context=context,
    )
    naics_region = next(r for r in regions if "NAICS Codes" in r.text)
    assert naics_region.region_type == "TOC_ENTRY"


def test_numbered_section_heading_detected() -> None:
    blocks = [_block(0, "C.1 SCOPE")]
    regions = classify_page_regions(
        page_number=17, blocks=blocks, tables=None, page_height=792.0
    )
    assert regions[0].region_type == "SUBSECTION_HEADING"


def test_lettered_section_heading_detected() -> None:
    blocks = [_block(0, "SECTION C - DESCRIPTION/SPECIFICATIONS/STATEMENT OF WORK")]
    regions = classify_page_regions(
        page_number=16, blocks=blocks, tables=None, page_height=792.0
    )
    assert regions[0].region_type == "SECTION_HEADING"


def test_narrative_sentence_is_narrative_not_heading() -> None:
    blocks = [
        _block(
            0,
            "The OCO should indicate in the task order solicitation whether "
            "or not Contractors shall submit labor pricing using the Master "
            "Contract's CONUS standardized labor categories in their task "
            "order proposals.",
        )
    ]
    regions = classify_page_regions(
        page_number=12, blocks=blocks, tables=None, page_height=792.0
    )
    assert regions[0].region_type == "NARRATIVE"


def test_form_field_label_shape_detected() -> None:
    blocks = [_block(0, "3. SOLICITATION NUMBER")]
    regions = classify_page_regions(
        page_number=2, blocks=blocks, tables=None, page_height=792.0
    )
    assert regions[0].region_type == "FORM_FIELD_LABEL"


def test_short_identifier_value_candidate_tagged_form_field_value() -> None:
    blocks = [_block(0, "47QRCA23R0001")]
    regions = classify_page_regions(
        page_number=2, blocks=blocks, tables=None, page_height=792.0
    )
    assert regions[0].region_type == "FORM_FIELD_VALUE"


def test_clause_listing_line_detected() -> None:
    # A real incorporated-clauses listing is a sustained run of many such
    # lines on one page (e.g. Section I) — CLAUSE_LISTING is gated on that
    # page-level density (like TOC_ENTRY is gated on TOC line density) so a
    # single isolated citation elsewhere in the document isn't mistaken for
    # part of an incorporation list. See test_isolated_clause_citation_not_listing.
    blocks = [
        _block(0, "52.202-1 Definitions JUN 2020", y0=100.0, y1=112.0),
        _block(1, "52.203-3 Gratuities APR 1984", y0=114.0, y1=126.0),
        _block(2, "52.204-21 Basic Safeguarding of Covered Info Systems", y0=128.0, y1=140.0),
    ]
    doc_context = build_document_context(pages=[(8, blocks, 792.0)])
    assert 8 in doc_context.clause_listing_pages

    regions = classify_page_regions(
        page_number=8, blocks=blocks, tables=None, page_height=792.0, doc_context=doc_context
    )
    assert regions[0].region_type == "CLAUSE_LISTING"


def test_isolated_clause_citation_not_listing() -> None:
    # A single citation on a page with no other clause lines nearby (e.g. an
    # incidental in-prose mention) must NOT be tagged CLAUSE_LISTING purely
    # because it matches the clause-number shape.
    blocks = [_block(0, "52.219-14 Limitations on Subcontracting")]
    regions = classify_page_regions(
        page_number=15, blocks=blocks, tables=None, page_height=792.0
    )
    assert regions[0].region_type != "CLAUSE_LISTING"


def test_table_row_matched_against_tables_json() -> None:
    tables = [
        {
            "headers": ["CLIN", "Description", "Amount"],
            "rows": [["0001", "Base Period", "600000000"]],
        }
    ]
    blocks = [
        _block(0, "CLIN Description Amount"),
        _block(1, "0001 Base Period 600000000"),
    ]
    regions = classify_page_regions(
        page_number=3, blocks=blocks, tables=tables, page_height=792.0
    )
    assert regions[0].region_type == "TABLE_HEADER"
    assert regions[1].region_type == "TABLE_ROW"


def test_repeated_footer_across_pages_is_footer_header() -> None:
    footer_text = "Contract No. 47QRCA25DSF07, Current as of Modification BASE"
    pages_data = []
    for page_number in range(1, 6):
        blocks = [
            _block(0, footer_text, y0=770.0, y1=780.0),
            _block(1, f"Page {page_number}", y0=780.0, y1=790.0),
        ]
        pages_data.append((page_number, blocks, 792.0))

    context = build_document_context(pages=pages_data)
    assert context.footer_header_templates

    regions = classify_page_regions(
        page_number=3,
        blocks=pages_data[2][1],
        tables=None,
        page_height=792.0,
        doc_context=context,
    )
    assert regions[0].region_type == "FOOTER_HEADER"


def test_degenerate_geometry_does_not_crash_and_falls_back() -> None:
    blocks = [
        _block(0, "2. CONTRACT NUMBER", x0=0.0, y0=0.0, x1=0.0, y1=0.0),
        _block(1, "47QRCA25DSF07", x0=0.0, y0=0.0, x1=0.0, y1=0.0),
    ]
    regions = classify_page_regions(
        page_number=2, blocks=blocks, tables=None, page_height=0.0
    )
    assert regions[0].region_type == "FORM_FIELD_LABEL"
    assert regions[1].region_type == "FORM_FIELD_VALUE"
    assert "degenerate_geometry_fallback" in regions[1].reason_codes


def test_empty_document_context_is_safe() -> None:
    context = build_document_context(pages=[])
    assert context == DocumentContext()
