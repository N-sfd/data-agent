from app.schemas.candidate_classification import ClassifiedCandidate, StructuralRegion
from app.services.candidate_router import (
    deduplicate_clin_funding_overlap,
    route_clause_citations,
    route_clin_rows,
    route_page_regions,
)
from app.services.clause_citation_scanner import ClauseCitation
from app.services.clin_block_detector import ParsedClinRow


def _region(
    region_type: str,
    text: str,
    *,
    page_number: int = 2,
    block_index: int = 0,
    bbox: tuple[float, float, float, float] | None = (72.0, 100.0, 300.0, 112.0),
    confidence: float = 0.8,
) -> StructuralRegion:
    return StructuralRegion(
        page_number=page_number,
        block_index=block_index,
        region_type=region_type,
        text=text,
        bbox=bbox,
        confidence=confidence,
    )


def test_form_field_label_pairs_with_nearby_identifier_value() -> None:
    label = _region(
        "FORM_FIELD_LABEL", "3. SOLICITATION NUMBER", block_index=0,
        bbox=(19.0, 47.0, 200.0, 59.0),
    )
    value = _region(
        "FORM_FIELD_VALUE", "47QRCA23R0001", block_index=1,
        bbox=(202.0, 53.0, 320.0, 63.0),
    )
    candidates = route_page_regions([label, value])
    matches = [c for c in candidates if c.label == "SOLICITATION NUMBER"]
    assert len(matches) == 1
    assert matches[0].category == "CONTRACT_SUMMARY"
    assert matches[0].value == "47QRCA23R0001"


def test_form_field_label_does_not_pair_with_distant_narrative_on_different_page() -> None:
    label = _region(
        "FORM_FIELD_LABEL", "3. SOLICITATION NUMBER", page_number=2, block_index=0,
    )
    # The confirmed-bad candidate value lives on a different page entirely -
    # this must never be classified as FORM_FIELD_VALUE by the structure
    # classifier in the first place, but even if it were, cross-page
    # association must be rejected here as a second line of defense.
    far_away_narrative = _region(
        "NARRATIVE",
        "The OCO should indicate in the task order solicitation whether or "
        "not Contractors shall submit labor pricing.",
        page_number=12,
        block_index=50,
    )
    candidates = route_page_regions([label, far_away_narrative])
    solicitation_candidates = [c for c in candidates if c.label == "SOLICITATION NUMBER"]
    assert len(solicitation_candidates) == 1
    assert solicitation_candidates[0].category == "QA_REVIEW"
    assert solicitation_candidates[0].value is None


def test_prose_shaped_value_rejected_even_when_adjacent() -> None:
    label = _region(
        "FORM_FIELD_LABEL", "3. SOLICITATION NUMBER", block_index=0,
        bbox=(19.0, 47.0, 200.0, 59.0),
    )
    # Adjacent in block order and on the same page, but clearly prose - must
    # not be accepted as the value.
    prose_value = _region(
        "FORM_FIELD_VALUE",
        "whether or not Contractors shall submit labor pricing",
        block_index=1,
        bbox=(19.0, 60.0, 400.0, 72.0),
    )
    candidates = route_page_regions([label, prose_value])
    matches = [c for c in candidates if c.label == "SOLICITATION NUMBER"]
    assert matches[0].category == "QA_REVIEW"
    assert matches[0].value is None


def test_toc_entry_routes_to_structural_heading_not_general_field() -> None:
    region = _region("TOC_ENTRY", "B.8.1 CONUS Standardized Labor Categories")
    candidates = route_page_regions([region])
    assert candidates[0].category == "STRUCTURAL_HEADING"


def test_footer_header_routes_to_noise() -> None:
    region = _region(
        "FOOTER_HEADER", "Contract No. 47QRCA25DSF07, Current as of Modification BASE"
    )
    candidates = route_page_regions([region])
    assert candidates[0].category == "NOISE"


def test_narrative_without_keyword_stays_narrative_category() -> None:
    region = _region(
        "NARRATIVE",
        "The contractor shall perform this requirement in accordance with "
        "the applicable technical standards referenced herein.",
    )
    candidates = route_page_regions([region])
    assert candidates[0].category == "NARRATIVE"


def test_narrative_with_attachment_keyword_routes_to_attachment() -> None:
    region = _region(
        "NARRATIVE",
        "The notice for prevailing wage rates is attached as Attachment (2) "
        "and provided for information only.",
    )
    candidates = route_page_regions([region])
    assert candidates[0].category == "ATTACHMENT"


def test_clin_rows_route_to_clin_category() -> None:
    row = ParsedClinRow(
        clin="10301",
        description="RD-541330-SB",
        quantity=None,
        unit=None,
        unit_price=None,
        amount="0.00",
        psc=None,
        pricing_arrangement=None,
        base_option=None,
        page_number=3,
        source_text="10301   RD-541330-SB    0.00",
        confidence=0.6,
    )
    candidates = route_clin_rows([row])
    assert candidates[0].category == "CLIN"
    assert candidates[0].value == "0.00"


def test_clause_listing_context_routes_far_to_clause() -> None:
    citation = ClauseCitation(
        clause_family="FAR",
        clause_number="52.202-1",
        title="Definitions",
        page_number=8,
        source_text="52.202-1 Definitions JUN 2020",
        listing_context=True,
    )
    candidates = route_clause_citations([citation])
    assert candidates[0].category == "CLAUSE"
    assert candidates[0].regulation == "FAR"


def test_clause_narrative_context_routes_far_to_reference() -> None:
    citation = ClauseCitation(
        clause_family="FAR",
        clause_number="52.219-14",
        title="",
        page_number=25,
        source_text="requirements of FAR 52.219-14, Limitations on Subcontracting",
        listing_context=False,
    )
    candidates = route_clause_citations([citation])
    assert candidates[0].category == "FAR_REFERENCE"


def test_dfars_always_routes_to_dfars_category() -> None:
    listing = ClauseCitation(
        clause_family="DFARS",
        clause_number="252.204-7012",
        title="Safeguarding Covered Defense Information",
        page_number=10,
        source_text="252.204-7012 Safeguarding Covered Defense Information",
        listing_context=True,
    )
    narrative = ClauseCitation(
        clause_family="DFARS",
        clause_number="252.216-7002",
        title="",
        page_number=41,
        source_text="select DFARS 252.216-7002, Alternate A",
        listing_context=False,
    )
    candidates = route_clause_citations([listing, narrative])
    assert all(c.category == "DFARS" for c in candidates)


def test_gsar_listing_routes_to_clause_with_gsar_regulation() -> None:
    citation = ClauseCitation(
        clause_family="GSAR",
        clause_number="552.216-75",
        title="Transactional Data Reporting",
        page_number=87,
        source_text="GSAR 552.216-75 Transactional Data Reporting. (MAY 2023)",
        listing_context=True,
    )
    candidates = route_clause_citations([citation])
    assert candidates[0].category == "CLAUSE"
    assert candidates[0].regulation == "GSAR"


def test_two_column_form_picks_same_column_value_not_nearest_row() -> None:
    # Confirmed regression: "28. AWARD DATE" (right column, x0~527) must
    # pair with "04/15/2025" (x0~532, same column) not "Esther Shannon"
    # (x0~20, left column, a different field) even though the latter was
    # closer in Y and appeared earlier in block order.
    label = _region(
        "FORM_FIELD_LABEL", "28. AWARD DATE", block_index=108,
        bbox=(527.75, 687.46, 571.95, 693.49),
    )
    wrong_column_value = _region(
        "FORM_FIELD_VALUE", "Esther Shannon", block_index=109,
        bbox=(20.15, 698.56, 98.69, 709.15),
    )
    correct_value = _region(
        "FORM_FIELD_VALUE", "04/15/2025", block_index=110,
        bbox=(532.55, 703.81, 588.65, 714.40),
    )
    candidates = route_page_regions([label, wrong_column_value, correct_value])
    matches = [c for c in candidates if c.label == "AWARD DATE"]
    assert matches[0].value == "04/15/2025"


def test_value_before_label_in_reading_order_never_paired() -> None:
    # Confirmed regression: a page-number stamp block ("1 / 91") appearing
    # just before "5. DATE ISSUED" in block order and geometrically above
    # it must not be picked as the value.
    page_stamp = _region(
        "FORM_FIELD_VALUE", "1\n 91", block_index=3,
        bbox=(504.0, 34.81, 544.44, 46.40),
    )
    label = _region(
        "FORM_FIELD_LABEL", "5. DATE ISSUED", block_index=4,
        bbox=(420.0, 46.61, 463.11, 52.64),
    )
    candidates = route_page_regions([page_stamp, label])
    matches = [c for c in candidates if c.label == "DATE ISSUED"]
    assert matches[0].value is None
    assert matches[0].category == "QA_REVIEW"


def test_semantic_validation_rejects_wrong_shaped_value_for_date_field() -> None:
    # Confirmed regression: "5. DATE ISSUED" must not accept a
    # solicitation-number-shaped value just because it was the nearest
    # available candidate after the real date field's own label was lost.
    label = _region(
        "FORM_FIELD_LABEL", "5. DATE ISSUED", block_index=4,
        bbox=(420.0, 46.6, 463.1, 52.6),
    )
    wrong_shaped_value = _region(
        "FORM_FIELD_VALUE", "47QRCA23R0001", block_index=7,
        bbox=(432.0, 52.8, 500.0, 63.4),
    )
    candidates = route_page_regions([label, wrong_shaped_value])
    matches = [c for c in candidates if c.label == "DATE ISSUED"]
    assert matches[0].category == "QA_REVIEW"
    assert matches[0].value is None
    assert any("does_not_parse_as_date" in r for r in matches[0].reason_codes)


def test_semantic_validation_accepts_correctly_shaped_date() -> None:
    label = _region(
        "FORM_FIELD_LABEL", "5. DATE ISSUED", block_index=4,
        bbox=(420.0, 46.6, 463.1, 52.6),
    )
    correct_value = _region(
        "FORM_FIELD_VALUE", "02/03/2025", block_index=6,
        bbox=(432.0, 58.8, 488.1, 69.4),
    )
    candidates = route_page_regions([label, correct_value])
    matches = [c for c in candidates if c.label == "DATE ISSUED"]
    # "Date Issued" is a recognized SF33 field (passes semantic validation)
    # but has no corresponding V3 Contract Summary column (only "Award
    # Date" does) - correctly GENERAL_ACCEPTED_FIELD, not invented into
    # Contract Summary.
    assert matches[0].category == "GENERAL_ACCEPTED_FIELD"
    assert matches[0].value == "02/03/2025"
    assert "semantic_validation_passed" in matches[0].reason_codes


def test_ambiguous_candidates_route_to_qa_review_preserving_both() -> None:
    label = _region(
        "FORM_FIELD_LABEL", "2. CONTRACT NUMBER", block_index=0,
        bbox=(19.0, 46.6, 81.2, 52.6),
    )
    # Two equally-plausible, equally-close, both-identifier-shaped values.
    candidate_a = _region(
        "FORM_FIELD_VALUE", "47QRCA25DSF07", block_index=1,
        bbox=(19.5, 52.8, 92.4, 63.4),
    )
    candidate_b = _region(
        "FORM_FIELD_VALUE", "47QRCA23R0001", block_index=2,
        bbox=(20.0, 53.0, 92.9, 63.6),
    )
    candidates = route_page_regions([label, candidate_a, candidate_b])
    matches = [c for c in candidates if c.label == "CONTRACT NUMBER"]
    assert matches[0].category == "QA_REVIEW"
    assert matches[0].value is None
    assert any("ambiguous" in r for r in matches[0].reason_codes)


def test_clin_funding_dedup_keeps_clin_drops_funding_duplicate() -> None:
    evidence = "10301   RD-541330-SB    0.00 Obligated Amount: $0.00"
    clin_candidate = ClassifiedCandidate(
        category="CLIN", confidence=0.6, source_page=3, evidence=evidence,
        region_type="TABLE_ROW", label="10301", value="0.00",
    )
    funding_candidate = ClassifiedCandidate(
        category="FUNDING", confidence=0.55, source_page=3, evidence=evidence,
        region_type="NARRATIVE",
    )
    unrelated = ClassifiedCandidate(
        category="FUNDING", confidence=0.55, source_page=4,
        evidence="Different funding narrative entirely", region_type="NARRATIVE",
    )
    result = deduplicate_clin_funding_overlap([clin_candidate, funding_candidate, unrelated])
    categories = [c.category for c in result]
    assert categories.count("FUNDING") == 1  # only the unrelated one survives
    assert categories.count("CLIN") == 1
    clin_result = next(c for c in result if c.category == "CLIN")
    assert "also_matched_funding_keyword_pattern_same_source_line" in clin_result.reason_codes


def test_unrecognized_label_still_preserved_as_general_accepted_field() -> None:
    label = _region(
        "FORM_FIELD_LABEL", "10. FOR INFORMATION CALL", block_index=0,
        bbox=(31.0, 224.0, 200.0, 236.0),
    )
    value = _region(
        "FORM_FIELD_VALUE", "Gabrina Daniels", block_index=1,
        bbox=(87.0, 234.0, 200.0, 246.0),
    )
    candidates = route_page_regions([label, value])
    matches = [c for c in candidates if c.value == "Gabrina Daniels"]
    assert matches[0].category == "GENERAL_ACCEPTED_FIELD"
