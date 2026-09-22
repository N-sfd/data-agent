from types import SimpleNamespace

from app.schemas.document_target import DocumentTarget
from app.services.generic_kv_scanner import (
    format_display_label,
    is_internal_form_name,
    is_plausible_kv_label,
    map_form_value_to_visible_label,
    scan_page_for_labeled_pairs,
)
from app.services.target_extraction_service import (
    _resolve_scalar_from_source_examples,
    _resolve_scalar_target,
)


def _page(number: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        page_number=number,
        final_text=text,
        form_fields_json={},
    )


def _kv_target(**overrides) -> DocumentTarget:
    defaults = {
        "id": "doc:kv_administra",
        "key": "kv_administra",
        "label": "Administrative Contracting Officer",
        "target_type": "field",
        "page_numbers": [3],
        "confidence": 0.82,
        "source_examples": [
            "'Administrative Contracting Officer: Jane A. Smith' on page 3 (inline_regex)"
        ],
    }
    defaults.update(overrides)
    return DocumentTarget(**defaults)


def test_resolve_scalar_from_source_examples_uses_discovery_evidence() -> None:
    page = _page(
        3,
        "Administrative Contracting Officer: Jane A. Smith\nOther contract text.",
    )
    target = _kv_target()

    result = _resolve_scalar_from_source_examples(
        target,
        page_lookup={3: page},
    )

    assert result is not None
    assert result.value == "Jane A. Smith"
    assert result.extraction_method == "source_evidence"
    assert result.verified is True
    assert result.confidence_detail is not None
    assert result.confidence_detail.signals.exact_label_match is True
    assert result.validation is not None
    assert result.validation.status == "passed"
    assert result.retrieval is not None
    assert result.retrieval.deterministic_status == "resolved"
    assert result.retrieval.ai_fallback_required is False


def test_resolve_scalar_target_prefers_source_evidence_over_label_search() -> None:
    page = _page(
        3,
        "Administrative Contracting Officer: Jane A. Smith",
    )
    target = _kv_target(label="Unrelated label text")

    result = _resolve_scalar_target(
        target,
        page_lookup={3: page},
        all_pages=[page],
    )

    assert result[0] is not None
    assert result[0].value == "Jane A. Smith"
    assert result[0].retrieval is not None
    assert result[0].retrieval.deterministic_status == "resolved"
    assert result[2] is False


def test_prose_fragments_are_not_plausible_kv_labels() -> None:
    assert is_plausible_kv_label("Administrative Contracting Officer") is True
    assert is_plausible_kv_label("SOLICITATION NO.") is True
    assert is_plausible_kv_label("PSC CD") is True
    assert (
        is_plausible_kv_label(
            "labor category in the task order shall be proposed"
        )
        is False
    )
    assert (
        is_plausible_kv_label(
            "LABOR CATEGORY IN THE TASK ORDER SHALL BE PROPO"
        )
        is False
    )
    assert is_plausible_kv_label("prevail in the locality") is False
    assert is_plausible_kv_label("PREVAIL IN THE LOCALIT") is False
    assert (
        is_plausible_kv_label(
            "task orders for those task orders requiring tra"
        )
        is False
    )
    assert (
        is_plausible_kv_label(
            "TASK ORDERS FOR THOSE TASK ORDERS REQUIRING TRA"
        )
        is False
    )

    # XFA / AcroForm internal field paths
    assert (
        is_plausible_kv_label("topmostSubform[0].Page1[0].PG11I[0]")
        is False
    )
    assert (
        is_plausible_kv_label("form1[0].Page2[0].TextField[3]")
        is False
    )


def test_is_internal_form_name_uses_multi_signal_scoring() -> None:
    # Strong hierarchy paths
    assert is_internal_form_name("topmostSubform[0].Page1[0].PG11I[0]") is True
    assert is_internal_form_name("form1[0].Page2[0].TextField[3]") is True
    assert is_internal_form_name("xfa.form.root") is True
    assert is_internal_form_name("#subform[2]") is True

    # Pure widget / page tokens
    assert is_internal_form_name("Page1") is True
    assert is_internal_form_name("PG11I") is True
    assert is_internal_form_name("CheckBox1") is True
    assert is_internal_form_name("TextField3") is True
    assert is_internal_form_name("") is True

    # Lone bracket index is NOT enough (legitimate labels may contain [0])
    assert is_internal_form_name("Item [0] Code") is False
    assert is_internal_form_name("Schedule [1]") is False

    # Real business labels should NOT be internal
    assert is_internal_form_name("SOLICITATION NO.") is False
    assert is_internal_form_name("Solicitation No.") is False
    assert is_internal_form_name("Contract Number") is False
    assert is_internal_form_name("Contract Form Number") is False
    assert is_internal_form_name("DODAAC") is False
    assert is_internal_form_name("Effective Date") is False
    assert is_internal_form_name("WAWF Payment Office") is False


def test_format_display_label() -> None:
    assert format_display_label("SOLICITATION NO.") == "Solicitation No."
    assert format_display_label("CONTRACT NO") == "Contract No."
    assert format_display_label("DATE ISSUED") == "Date Issued"
    assert (
        format_display_label("REQUISITION/PURCHASE REQUEST/PROJECT NO.")
        == "Requisition / Purchase Request / Project No."
    )
    assert format_display_label("DODAAC") == "DODAAC"
    assert format_display_label("PSC CD") == "PSC CD"
    assert format_display_label("WAWF Payment Office") == "WAWF Payment Office"


def test_map_form_value_to_visible_label() -> None:
    text = (
        "SOLICITATION NO. FA300224C0008\n"
        "CONTRACT NO.\n"
        "FA300224C0009\n"
        "Other contract text."
    )
    assert (
        map_form_value_to_visible_label(text, "FA300224C0008")
        == "Solicitation No."
    )
    assert (
        map_form_value_to_visible_label(text, "FA300224C0009")
        == "Contract No."
    )
    assert map_form_value_to_visible_label(text, "MISSING") is None
    assert (
        map_form_value_to_visible_label(
            "topmostSubform[0].Page1[0]: FA300224C0008",
            "FA300224C0008",
        )
        is None
    )


def test_scan_xfa_form_maps_to_readable_label_with_provenance() -> None:
    page = SimpleNamespace(
        page_number=1,
        final_text="SOLICITATION NO. FA300224C0008\nIssued By: ACC",
        form_fields_json={
            "topmostSubform[0].Page1[0].PG11I[0]": "FA300224C0008",
            "topmostSubform[0].Page1[0].PG99Z[0]": "NO_VISIBLE_LABEL_VALUE",
        },
        tables_json=[],
    )
    pairs = scan_page_for_labeled_pairs(page=page)
    labels = {pair.raw_label for pair in pairs}

    assert "Solicitation No." in labels
    assert not any("topmostSubform" in label for label in labels)
    assert not any("PG11I" in label for label in labels)
    assert not any("[0]" in label for label in labels)
    assert "NO_VISIBLE_LABEL_VALUE" not in {pair.value for pair in pairs}

    mapped = next(p for p in pairs if p.raw_label == "Solicitation No.")
    assert mapped.source_field_path == "topmostSubform[0].Page1[0].PG11I[0]"


def test_scan_acroform_human_label_is_kept() -> None:
    page = SimpleNamespace(
        page_number=1,
        final_text="Contract Number: ABC-123\nEffective Date: 2024-01-15",
        form_fields_json={
            "Contract Number": "ABC-123",
            "Effective Date": "2024-01-15",
        },
        tables_json=[],
    )
    pairs = scan_page_for_labeled_pairs(page=page)
    labels = {pair.raw_label for pair in pairs}

    assert "Contract Number" in labels
    assert "Effective Date" in labels
    assert all(p.source_field_path is None for p in pairs if p.method == "form_field")


def test_scan_ordinary_text_pdf_keeps_human_labels() -> None:
    page = SimpleNamespace(
        page_number=1,
        final_text=(
            "SOLICITATION NO. FA300224C0008\n"
            "DATE ISSUED: 15 JAN 2024\n"
            "DODAAC: HQ0338\n"
        ),
        form_fields_json={},
        tables_json=[],
    )
    pairs = scan_page_for_labeled_pairs(page=page)
    labels = {pair.raw_label for pair in pairs}

    assert "Solicitation No." in labels
    assert "Date Issued" in labels
    assert "DODAAC" in labels
    assert not any("topmostSubform" in label for label in labels)
    assert not any(is_internal_form_name(label) for label in labels)


def test_toc_dotted_leader_evidence_is_not_promoted_as_a_field() -> None:
    """'ATTACHMENT J-1 ........ 69' is a table-of-contents navigation
    line, not an extracted business-field value, even when discovery
    picked it up as a kv_* candidate with high OCR confidence."""
    page = _page(
        1,
        "TABLE OF CONTENTS\nATTACHMENT J-1 ........................ 69\n",
    )
    target = _kv_target(
        id="doc:kv_attachment_j_1",
        key="kv_attachment_j_1",
        label="Attachment J-1",
        page_numbers=[1],
        confidence=0.99,
        source_examples=[
            "'Attachment J-1: ........................ 69' on page 1 (inline_regex)"
        ],
    )

    result = _resolve_scalar_from_source_examples(target, page_lookup={1: page})

    assert result is None


def test_clause_citation_evidence_is_not_promoted_as_a_field() -> None:
    """'505(b)(6), Post-award Notices and Debriefings' is a FAR clause
    citation/reference, not a scalar business-field value."""
    page = _page(
        4,
        "FAR 16 references 505(b)(6), Post-award Notices and Debriefings\n",
    )
    target = _kv_target(
        id="doc:kv_far_16",
        key="kv_far_16",
        label="Far 16",
        page_numbers=[4],
        confidence=0.99,
        source_examples=[
            "'Far 16: 505(b)(6), Post-award Notices and Debriefings' on page 4 (inline_regex)"
        ],
    )

    result = _resolve_scalar_from_source_examples(target, page_lookup={4: page})

    assert result is None


def test_no_candidate_returns_none_instead_of_default_confidence() -> None:
    """When nothing at all is found for a target, the resolver should
    return None (so the caller can escalate to AI / mark Not Found)
    rather than manufacturing a fixed ~25% Needs Review row."""
    page = _page(2, "This page has no relevant labels or values at all.")
    page.id = 2
    target = _kv_target(
        id="doc:contacts",
        key="contacts",
        label="Contacts",
        page_numbers=[2],
        confidence=0.5,
        source_examples=[],
    )

    result, retrieval, escalate = _resolve_scalar_target(
        target,
        page_lookup={2: page},
        all_pages=[page],
    )

    assert result is None
    assert escalate is True


def test_resolved_scalar_inherits_section_from_document_outline() -> None:
    """A field resolved on a page with no heading of its own must still
    carry the section it structurally belongs to, inherited from the
    nearest preceding heading anywhere earlier in the document — not
    left blank just because the value and the heading are on different
    pages."""
    page_23 = _page(23, "SECTION G\nCONTRACT ADMINISTRATION DATA\n")
    page_24 = _page(
        24, "WAWF Payment Office: DFAS Columbus routing data follows."
    )
    target = _kv_target(
        id="doc:wawf_payment_office",
        key="wawf_payment_office",
        label="WAWF Payment Office",
        page_numbers=[24],
        confidence=0.86,
        source_examples=[
            "'WAWF Payment Office: DFAS Columbus routing data follows.' on page 24 (field_probe)"
        ],
    )

    from app.services.document_outline import build_document_outline

    outline = build_document_outline([page_23, page_24])

    result = _resolve_scalar_from_source_examples(
        target,
        page_lookup={23: page_23, 24: page_24},
        outline=outline,
    )

    assert result is not None
    assert result.evidence.section == "G — Contract Administration Data"


def test_field_probe_evidence_resolves_via_source_examples() -> None:
    """WAWF Payment Office and similar field-probe targets store evidence
    in the format  'PROBE_LABEL: value' on page N (field_probe)  and
    should resolve from that evidence string."""
    page = _page(
        5,
        "PAYMENT OFFICE: HQ0338\nSome other contract text.",
    )
    target = _kv_target(
        id="doc:wawf_payment_office",
        key="wawf_payment_office",
        label="WAWF Payment Office",
        page_numbers=[5],
        confidence=0.86,
        source_examples=[
            "'PAYMENT OFFICE: HQ0338' on page 5 (field_probe)"
        ],
    )

    result = _resolve_scalar_from_source_examples(
        target,
        page_lookup={5: page},
    )

    assert result is not None
    assert result.value == "HQ0338"
    assert result.extraction_method == "source_evidence"
    assert result.verified is True
