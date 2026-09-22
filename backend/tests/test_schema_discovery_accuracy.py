import asyncio
from types import SimpleNamespace

from app.services.ai_provider import DisabledAIProvider
from app.services.schema_discovery import discover_document_schema
from app.services.structure_detection import detect_document_structures


def _page(
    *,
    number: int,
    text: str,
    tables: list[dict] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        page_number=number,
        final_text=text,
        tables_json=tables or [],
        form_fields_json={},
    )


def _document() -> SimpleNamespace:
    return SimpleNamespace(
        id="doc-test",
        original_filename="solicitation.pdf",
    )


async def _detect(text: str, tables: list[dict] | None = None):
    return await detect_document_structures(
        document=_document(),
        pages=[_page(number=1, text=text, tables=tables)],
        ai_provider=DisabledAIProvider(),
    )


async def _discover(text: str, tables: list[dict] | None = None):
    return await discover_document_schema(
        document=_document(),
        pages=[_page(number=1, text=text, tables=tables)],
        ai_provider=DisabledAIProvider(),
    )


def _assert_no_pricing_or_rate_card(targets) -> None:
    keys = {target.key for target in targets}
    labels = {target.label for target in targets}
    assert "rate_card" not in keys
    assert "pricing_table" not in keys
    assert "Rate Card" not in labels
    assert "Pricing Table" not in labels


def test_gov_contract_without_pricing_does_not_surface_rate_card_or_pricing_table() -> None:
    text = (
        "SOLICITATION NO.  W912HQ-24-R-0001\n"
        "CONTRACT NO.  W912HQ-24-C-0001\n"
        "NAICS  541512\n"
        "PSC CD  R499\n"
        "MAX NET AMT  $500,000.00\n"
        "Schedule of supplies/services for CLIN 0001 with unit prices."
    )
    tables = [
        {
            "headers": ["Labor Category", "Hourly Rate", "Hours"],
            "rows": [{"Labor Category": "Senior Analyst", "Hourly Rate": "$150", "Hours": "100"}],
        }
    ]

    detection = asyncio.run(_detect(text, tables))
    all_detected = detection.detected_targets + detection.possible_targets
    _assert_no_pricing_or_rate_card(all_detected)

    schema = asyncio.run(_discover(text, tables))
    _assert_no_pricing_or_rate_card(schema.targets)


def test_gov_form_labels_are_discoverable() -> None:
    text = (
        "SOLICITATION NO.  W912HQ-24-R-0001\n"
        "CONTRACT NO.  W912HQ-24-C-0001\n"
        "DODAAC  W58RGZ\n"
        "CAGE  1ABC2\n"
        "WAWF Payment Office routing data follows."
    )

    schema = asyncio.run(_discover(text))

    keys = {target.key for target in schema.targets}
    labels = {target.label.lower() for target in schema.targets}

    assert "solicitation_number" in keys or any("solicitation" in label for label in labels)
    assert "contract_no" in keys or "contract_number" in keys or any(
        "contract no" in label for label in labels
    )
    assert "dodaac" in keys or any("dodaac" in label for label in labels)


def test_toc_dotted_leaders_are_not_discovered_as_business_fields() -> None:
    text = (
        "TABLE OF CONTENTS\n"
        "ATTACHMENT J-1 ........................ 69\n"
        "ATTACHMENT J-2 ........................ 72\n"
        "ATTACHMENT J-10 ....................... 122\n"
        "SECTION B ..................... 9\n"
    )

    schema = asyncio.run(_discover(text))

    keys = {target.key for target in schema.targets}
    values = {
        " ".join(str(e) for e in target.source_examples).lower()
        for target in schema.targets
    }

    assert "kv_attachment_j_1" not in keys
    assert "kv_attachment_j_2" not in keys
    assert "kv_attachment_j_10" not in keys
    assert not any("........" in value for value in values)


def test_clause_citation_reference_is_not_discovered_as_a_business_field() -> None:
    text = (
        "FAR 16 clause reference: 505(b)(6), Post-award Notices and Debriefings\n"
    )

    schema = asyncio.run(_discover(text))

    keys = {target.key for target in schema.targets}
    assert "kv_far_16" not in keys


def test_ucf_section_heading_and_form_noise_are_not_discovered_as_fields() -> None:
    text = (
        "E. Inspection and Acceptance: All items must pass final inspection.\n"
        "Address: (Type or print)\n"
        "Area Code Number: EXT.\n"
        "CLIN: DESCRIPTION OF SUPPLIES/SERVICES AMOUNT\n"
        "Government: Government property includes both Government-furnished "
        "and contractor-acquired property necessary to perform this contract.\n"
        "Contract Number: 47QRCA25DSF07\n"
    )

    schema = asyncio.run(_discover(text))

    keys = {target.key for target in schema.targets}
    assert "kv_e_inspection_and_acceptance" not in keys
    assert "kv_address" not in keys
    assert "kv_area_code_number" not in keys
    assert "kv_clin" not in keys
    assert "kv_government" not in keys
    assert "contract_number" in keys
