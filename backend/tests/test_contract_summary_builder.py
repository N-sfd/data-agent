"""Regression tests for the Ceiling / Max Aggregate vs Minimum Guarantee
contamination bug (V3 ground-truth quality gate): the SF33 "20. AMOUNT"
form field is an award/obligated amount, which for this contract equals
the Minimum Guarantee — it must never also populate Ceiling / Max
Aggregate. Ceiling / Max Aggregate must come only from its own explicit
ceiling language.
"""

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.contract_summary_builder import build_contract_summary
from app.services.contract_summary_fields import FIELD_KEY_TO_V3_COLUMN
from app.schemas.candidate_classification import ClassifiedCandidate

_DOCUMENT = Document(id="doc-1", original_filename="contract.pdf")


def _amount_candidate() -> ClassifiedCandidate:
    return ClassifiedCandidate(
        category="CONTRACT_SUMMARY",
        value="$2,500.00",
        source_page=2,
        evidence="20. AMOUNT -> $2,500.00",
        confidence=0.85,
        reason_codes=["field_key_amount"],
        region_type="FORM_FIELD_VALUE",
    )


def test_amount_field_key_not_mapped_to_ceiling_column() -> None:
    # The confirmed bug: this mapping silently duplicated an award-action
    # amount into the contract ceiling column.
    assert "amount" not in FIELD_KEY_TO_V3_COLUMN


def test_ceiling_and_minimum_guarantee_stay_distinct_when_source_says_unlimited() -> None:
    pages = [
        DocumentPage(
            document_id=_DOCUMENT.id,
            page_number=11,
            final_text=(
                "B.4 MINIMUM CONTRACT GUARANTEE AND MAXIMUM CONTRACT CEILING\n"
                "(a) Minimum Guarantee. The minimum guaranteed award amount for "
                "this IDIQ contract is $2,500.00 per contract for the full term "
                "of the Master Contract.\n"
                "(c) Maximum Ceiling. As authorized by CD-2023-01, there is no "
                "maximum dollar ceiling for the Master Contract or for each "
                "individual task order."
            ),
        )
    ]

    summary = build_contract_summary(
        document=_DOCUMENT, pages=pages, candidates=[_amount_candidate()]
    )

    assert summary.minimum_guarantee == "$2,500.00"
    assert summary.ceiling_max_aggregate == "No maximum dollar ceiling (unlimited task order value)"
    assert summary.ceiling_max_aggregate != summary.minimum_guarantee


def test_ceiling_falls_back_to_explicit_dollar_figure_when_stated() -> None:
    pages = [
        DocumentPage(
            document_id=_DOCUMENT.id,
            page_number=11,
            final_text=(
                "The minimum guarantee for this contract is $2,500.00. "
                "The maximum contract ceiling for this IDIQ is $50,000,000.00."
            ),
        )
    ]

    summary = build_contract_summary(document=_DOCUMENT, pages=pages, candidates=[])

    assert summary.minimum_guarantee == "$2,500.00"
    assert summary.ceiling_max_aggregate == "$50,000,000.00"


def test_ceiling_stays_blank_when_no_ceiling_language_present() -> None:
    pages = [
        DocumentPage(
            document_id=_DOCUMENT.id,
            page_number=1,
            final_text="20. AMOUNT $2,500.00",
        )
    ]

    summary = build_contract_summary(
        document=_DOCUMENT, pages=pages, candidates=[_amount_candidate()]
    )

    # No ceiling-specific language anywhere -> Needs Review, not fabricated
    # from the unrelated SF33 amount field.
    assert summary.ceiling_max_aggregate is None
