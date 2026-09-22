"""Regression tests for document-wide structural section detection."""

from types import SimpleNamespace

from app.services.document_outline import build_document_outline, resolve_section


def _page(number: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(page_number=number, final_text=text)


def test_sf33_cover_page_detected() -> None:
    pages = [
        _page(1, "SOLICITATION, OFFER AND AWARD\n1. THIS CONTRACT IS A RATED ORDER"),
    ]
    outline = build_document_outline(pages)
    info = resolve_section(outline, page_number=1, offset=0)
    assert info is not None
    assert info.section_code == "SF33"


def test_section_heading_detected_and_carries_forward_across_pages() -> None:
    pages = [
        _page(1, "SOLICITATION, OFFER AND AWARD"),
        _page(23, "SECTION G\nCONTRACT ADMINISTRATION DATA\nG.3.1 Payment office follows."),
        _page(24, "WAWF Payment Office: DFAS Columbus routing data follows."),
        _page(25, "More Section G content with no heading on this page."),
    ]
    outline = build_document_outline(pages)

    on_heading_page = resolve_section(outline, page_number=23, offset=0)
    assert on_heading_page is not None
    assert on_heading_page.section_code == "G"
    assert on_heading_page.section_title == "Contract Administration Data"

    # No heading at all on page 24 or 25 — must inherit Section G from
    # page 23, not read as unknown.
    carried_24 = resolve_section(outline, page_number=24, offset=0)
    assert carried_24 is not None
    assert carried_24.section_code == "G"

    carried_25 = resolve_section(outline, page_number=25, offset=0)
    assert carried_25 is not None
    assert carried_25.section_code == "G"


def test_subsection_heading_captured() -> None:
    pages = [
        _page(23, "SECTION G\nCONTRACT ADMINISTRATION DATA"),
        _page(24, "G.3.1 Payment Office\nDFAS Columbus handles payment."),
    ]
    outline = build_document_outline(pages)
    info = resolve_section(outline, page_number=24, offset=0)
    assert info is not None
    assert info.section_code == "G"
    assert info.subsection_code == "G.3.1"


def test_mid_page_section_start_resolves_by_offset() -> None:
    text = (
        "Trailing content from Section B continues here for a while.\n"
        "SECTION C\n"
        "DESCRIPTION/SPECIFICATIONS/STATEMENT OF WORK\n"
        "Work begins upon award."
    )
    pages = [_page(8, text)]
    outline = build_document_outline(pages)

    before_heading = text.index("Trailing")
    after_heading = text.index("Work begins")

    before_info = resolve_section(outline, page_number=8, offset=before_heading)
    after_info = resolve_section(outline, page_number=8, offset=after_heading)

    assert after_info is not None
    assert after_info.section_code == "C"
    # Position before the heading must not inherit Section C.
    assert before_info is None or before_info.section_code != "C"


def test_toc_page_is_not_treated_as_a_section_boundary() -> None:
    pages = [
        _page(
            2,
            (
                "TABLE OF CONTENTS\n"
                "SECTION B ........................ 3\n"
                "SECTION C ........................ 8\n"
                "SECTION G ........................ 23\n"
            ),
        ),
        _page(3, "SECTION B\nSUPPLIES OR SERVICES AND PRICES/COSTS\nCLIN 0001."),
    ]
    outline = build_document_outline(pages)

    # The TOC page itself must not register Section B/C/G as starting
    # there — only the real heading on page 3 should be a boundary.
    boundaries_on_toc_page = [b for b in outline if b.page_number == 2]
    assert boundaries_on_toc_page == []

    real_boundary = resolve_section(outline, page_number=3, offset=0)
    assert real_boundary is not None
    assert real_boundary.section_code == "B"


def test_no_heading_anywhere_yields_no_section() -> None:
    pages = [_page(1, "This document has no structural headings at all.")]
    outline = build_document_outline(pages)
    assert resolve_section(outline, page_number=1, offset=0) is None


def test_attachment_and_exhibit_boundaries() -> None:
    pages = [
        _page(69, "ATTACHMENT J-1\nPAST PERFORMANCE QUESTIONNAIRE"),
        _page(90, "EXHIBIT A\nPRICING WORKSHEET"),
    ]
    outline = build_document_outline(pages)

    attachment = resolve_section(outline, page_number=69, offset=0)
    assert attachment is not None
    assert attachment.section_code == "Attachment J-1"

    exhibit = resolve_section(outline, page_number=90, offset=0)
    assert exhibit is not None
    assert exhibit.section_code == "Exhibit A"
