"""Regression: narrative kv_* must not enter normalized.fields."""

from app.services.field_classification import (
    is_canonical_business_field,
    is_narrative_or_section_field,
)
from app.services.reviewed_export import build_normalized_document


class _Doc:
    id = "doc-1"
    original_filename = "Contract_47QRCA25DSF07.pdf"


class _Field:
    def __init__(self, key, label, value, group="field"):
        self.field_key = key
        self.label = label
        self.value = value
        self.field_group = group
        self.review_status = "pending"
        self.confidence = 0.99
        self.evidence_json = {}
        self.original_value = value
        self.extraction_method = "label_value"


def test_narrative_kv_keys_excluded_from_normalized_fields() -> None:
    fields = [
        _Field("contract_number", "Contract Number", "47QRCA25DSF07"),
        _Field("kv_a_name", "A. NAME", "Gabrina Daniels"),
        _Field(
            "kv_b_1_general",
            "B.1 General",
            "This section describes the general requirements for the effort "
            * 3,
        ),
        _Field(
            "kv_c_1_scope",
            "C.1 Scope",
            "The contractor shall provide a total solution covering "
            * 4,
        ),
    ]

    assert is_canonical_business_field(
        key="contract_number", label="Contract Number", value="47QRCA25DSF07"
    )
    assert is_canonical_business_field(
        key="kv_a_name", label="A. NAME", value="Gabrina Daniels"
    )
    assert is_narrative_or_section_field(
        key="kv_b_1_general",
        label="B.1 General",
        value=fields[2].value,
    )

    normalized = build_normalized_document(document=_Doc(), fields=fields)
    assert "contract_number" in normalized["fields"]
    assert "kv_b_1_general" not in normalized["fields"]
    assert "b_1_general" not in normalized["fields"]
    assert "kv_c_1_scope" not in normalized["fields"]
    assert "c_1_scope" not in normalized["fields"]
    # Short form-style A. NAME / 10A. NAME stays as a business field. The
    # public normalized-document map uses the canonical (kv_-stripped) key
    # — the raw candidate key never appears in an export/API surface.
    assert "kv_a_name" not in normalized["fields"]
    assert normalized["fields"].get("a_name") == "Gabrina Daniels"


def test_structural_reference_candidates_are_never_business_fields() -> None:
    """Exact P0 regression examples: paragraph/section/appendix pointers
    picked up by the kv_ scanner must never reach normalized.fields, no
    matter how clean their OCR-read value looks."""

    structural = [
        ("kv_pws_section_11_para", "PWS Section 11 Para", "11.1.1. except"),
        ("kv_pws_section_12_para", "PWS Section 12 Para", "12.1.3.2.1."),
        ("kv_pws_section_23_para", "PWS Section 23 Para", "23.1.3"),
        ("kv_section_10_para", "Section 10 Para", "10.1.2.2."),
        ("kv_section_12_para", "Section 12 Para", "12.1.2.14.1."),
        ("kv_section_7_para", "Section 7 Para", "7.1.5.3."),
        ("kv_para", "Para", "7.1.5.4."),
        ("kv_appendix_2f", "Appendix 2F", "1.2.2. (Cost"),
    ]
    for key, label, value in structural:
        assert is_narrative_or_section_field(
            key=key, label=label, value=value
        ), f"{key} ({value!r}) must classify as section/reference, not a field"
        assert not is_canonical_business_field(
            key=key, label=label, value=value
        ), f"{key} must not be a canonical business field"

    legitimate = [
        ("kv_pr_number", "PR Number", "F2X3C34150A001"),
        ("kv_pr_line_item_number", "PR Line Item Number", "0001"),
        ("kv_pricing_arrangement", "Pricing Arrangement", "Firm Fixed Price"),
        ("kv_product_service_code", "Product/Service Code", "S216"),
    ]
    for key, label, value in legitimate:
        assert is_canonical_business_field(
            key=key, label=label, value=value
        ), f"{key} ({value!r}) is a legitimate business field and must be promoted"

    fields = [
        _Field(key, label, value) for key, label, value in structural + legitimate
    ]
    normalized = build_normalized_document(document=_Doc(), fields=fields)
    for key, _label, _value in structural:
        canonical = key[3:]
        assert key not in normalized["fields"]
        assert canonical not in normalized["fields"]
    for key, _label, value in legitimate:
        canonical = key[3:]
        assert key not in normalized["fields"]
        assert normalized["fields"].get(canonical) == value
