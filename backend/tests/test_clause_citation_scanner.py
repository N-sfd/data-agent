from types import SimpleNamespace

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
