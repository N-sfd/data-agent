from app.services.structure_detection import _label_from_headers


def test_pricing_table_requires_literal_heading():
    key, label, confidence, _evidence = _label_from_headers(
        headers=["Item", "Unit Price", "Total Price"],
        surrounding_text="Schedule of supplies and services with unit prices.",
        page_number=3,
        index=0,
    )

    assert key != "pricing_table"
    assert label != "Pricing Table"
    # May surface as Supplies/Services or an unlabeled document table.
    assert key in {"supplies_services", "line_items"} or key.startswith("table_p")
    assert confidence < 0.95 or key == "supplies_services"


def test_rate_card_requires_literal_heading():
    key, label, confidence, _evidence = _label_from_headers(
        headers=["Labor Category", "Hourly Rate", "Hours"],
        surrounding_text="Labor categories and hourly rates for CLIN 0001.",
        page_number=5,
        index=1,
    )

    assert key != "rate_card"
    assert label != "Rate Card"
    # Header-aligned labeling may select Labor Categories, but never Rate Card.
    assert key in {"labor_categories", "hourly_rates"} or key.startswith("table_p")


def test_page_heading_does_not_relabel_unrelated_table():
    """A distant 'Pricing Table' phrase must not rename a delivery table."""
    key, label, _confidence, _evidence = _label_from_headers(
        headers=["Milestone", "Delivery Date", "Location"],
        surrounding_text=(
            "PRICING TABLE appears earlier in this solicitation.\n\n"
            "Delivery milestones for CLIN 0002 follow below."
        ),
        page_number=6,
        index=1,
    )

    assert key != "pricing_table"
    assert label != "Pricing Table"


def test_rate_card_matches_literal_heading():
    key, label, confidence, evidence = _label_from_headers(
        headers=["Category", "Rate"],
        surrounding_text="RATE CARD\nLabor rates effective FY2024.",
        page_number=2,
        index=0,
    )

    assert key == "rate_card"
    assert label == "Rate Card"
    assert confidence >= 0.9
    assert any("Rate Card" in item for item in evidence)


def test_pricing_table_matches_literal_heading():
    key, label, confidence, _evidence = _label_from_headers(
        headers=["SKU", "Qty", "Amount"],
        surrounding_text="PRICING TABLE for option year 1.",
        page_number=4,
        index=0,
    )

    assert key == "pricing_table"
    assert label == "Pricing Table"
    assert confidence >= 0.9
