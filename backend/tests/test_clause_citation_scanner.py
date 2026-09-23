from types import SimpleNamespace

from app.schemas.candidate_classification import StructuralRegion
from app.services.clause_citation_scanner import scan_pages_for_clause_citations
from app.services.target_extraction_service import _resolve_clause_target
from app.schemas.document_target import DocumentTarget


def _page(number: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        page_number=number,
        final_text=text,
    )


def test_scan_far_and_dfars_clause_numbers_from_page_text() -> None:
    page = _page(
        2,
        (
            "Clauses Incorporated by Reference\n"
            "52.212-4 Contract Terms and Conditions - Commercial Items (NOV 2023)\n"
            "252.204-7012 Safeguarding Covered Defense Information (JAN 2023)"
        ),
    )

    citations = scan_pages_for_clause_citations(pages=[page])

    numbers = {item.clause_number for item in citations}
    assert "52.212-4" in numbers
    assert "252.204-7012" in numbers


def test_scan_gsar_clause_numbers_distinct_from_far() -> None:
    page = _page(
        87,
        "GSAR 552.216-75 Transactional Data Reporting. (MAY 2023)\n"
        "FAR 52.204-21 Basic Safeguarding of Covered Contractor Information Systems.",
    )

    citations = scan_pages_for_clause_citations(pages=[page])

    families_by_number = {item.clause_number: item.clause_family for item in citations}
    assert families_by_number["552.216-75"] == "GSAR"
    assert families_by_number["52.204-21"] == "FAR"
    # GSAR pattern must never misfire on the FAR/DFARS numbers and vice
    # versa (shared "52" substring inside "552").
    assert "52.216-75" not in families_by_number
    assert "252.216-75" not in families_by_number


def test_listing_context_reported_when_regions_supplied() -> None:
    page = _page(8, "52.202-1 Definitions JUN 2020")
    listing_region = StructuralRegion(
        page_number=8,
        block_index=0,
        region_type="CLAUSE_LISTING",
        text="52.202-1 Definitions JUN 2020",
        confidence=0.9,
    )

    citations = scan_pages_for_clause_citations(
        pages=[page],
        regions_by_page={8: [listing_region]},
    )

    assert citations[0].listing_context is True


def test_listing_context_none_when_regions_not_supplied() -> None:
    page = _page(8, "52.202-1 Definitions JUN 2020")

    citations = scan_pages_for_clause_citations(pages=[page])

    assert citations[0].listing_context is None


def test_toc_line_referencing_clause_number_is_dropped_not_far_reference() -> None:
    # "I.2.1 FAR 52.216-32 Task-Order and Delivery-Order Ombudsman
    # (Alternate I) (Sept 2019)......74" is the document's own Table of
    # Contents entry for the clause, not a citation of it - it must not
    # become a FAR_REFERENCE candidate (confirmed regression: TOC noise
    # inflating the FAR_REFERENCE count).
    page = _page(
        9,
        "I.2.1 FAR 52.216-32 Task-Order and Delivery-Order Ombudsman "
        "(Alternate I) (Sept 2019)......................................74",
    )
    toc_region = StructuralRegion(
        page_number=9,
        block_index=0,
        region_type="TOC_ENTRY",
        text=page.final_text,
        confidence=0.95,
    )

    citations = scan_pages_for_clause_citations(
        pages=[page],
        regions_by_page={9: [toc_region]},
    )

    assert citations == []


def test_title_reconstructed_from_next_line_when_number_alone() -> None:
    # Confirmed pattern once line-level regions are used: the clause number
    # sits on its own line, with the title on the immediately following
    # line - the same-line regex capture alone would yield an empty title.
    page = _page(79, "52.204-21\nBasic Safeguarding of Covered Contractor Information Systems.")
    number_region = StructuralRegion(
        page_number=79, block_index=0, region_type="CLAUSE_LISTING",
        text="52.204-21", confidence=0.9,
    )
    title_region = StructuralRegion(
        page_number=79, block_index=1, region_type="NARRATIVE",
        text="Basic Safeguarding of Covered Contractor Information Systems.",
        confidence=0.7,
    )

    citations = scan_pages_for_clause_citations(
        pages=[page],
        regions_by_page={79: [number_region, title_region]},
    )

    assert citations[0].title == "Basic Safeguarding of Covered Contractor Information Systems"


def test_title_not_reconstructed_from_another_citation_line() -> None:
    page = _page(50, "52.204-21\n52.204-30")
    number_region = StructuralRegion(
        page_number=50, block_index=0, region_type="CLAUSE_LISTING",
        text="52.204-21", confidence=0.9,
    )
    next_citation_region = StructuralRegion(
        page_number=50, block_index=1, region_type="CLAUSE_LISTING",
        text="52.204-30", confidence=0.9,
    )

    citations = scan_pages_for_clause_citations(
        pages=[page],
        regions_by_page={50: [number_region, next_citation_region]},
    )

    first = next(c for c in citations if c.clause_number == "52.204-21")
    assert first.title == ""


def test_narrative_context_reported_false() -> None:
    page = _page(
        25,
        "Contractors not in full compliance with FAR 52.219-14, Limitations "
        "on Subcontracting, by the end of the period.",
    )
    narrative_region = StructuralRegion(
        page_number=25,
        block_index=0,
        region_type="NARRATIVE",
        text=page.final_text,
        confidence=0.75,
    )

    citations = scan_pages_for_clause_citations(
        pages=[page],
        regions_by_page={25: [narrative_region]},
    )

    assert citations[0].listing_context is False


def test_resolve_clause_target_returns_table_before_ai() -> None:
    page = _page(
        1,
        "FAR 52.212-4 Contract Terms and Conditions - Commercial Items (NOV 2023)",
    )
    target = DocumentTarget(
        id="doc:far_clauses",
        key="far_clauses",
        label="FAR Clauses",
        target_type="clause",
        page_numbers=[1],
        confidence=0.96,
    )

    result = _resolve_clause_target(
        target,
        page_lookup={1: page},
        all_pages=[page],
    )

    assert result is not None
    assert result.columns
    assert any(row["clause_number"] == "52.212-4" for row in result.rows)
