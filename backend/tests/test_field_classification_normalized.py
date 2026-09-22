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
    assert "kv_c_1_scope" not in normalized["fields"]
    # Short form-style A. NAME / 10A. NAME stays as a business field.
    assert normalized["fields"].get("kv_a_name") == "Gabrina Daniels"
