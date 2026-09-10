from app.services.discovery_enrichment import (
    assign_discovery_group,
    canonical_display_name,
    infer_value_type,
)
from app.services.generic_kv_scanner import is_internal_form_name


def test_canonical_display_aliases_are_enhancements_not_schema() -> None:
    assert canonical_display_name("SOLICITATION NO.") == "Solicitation Number"
    assert canonical_display_name("Contract No") == "Contract Number"
    # Unknown fields stay schema-agnostic — no dictionary required.
    assert (
        canonical_display_name("Hemoglobin Result") == "Hemoglobin Result"
    )
    assert (
        canonical_display_name("Research Objective") == "Research Objective"
    )


def test_discovery_groups_are_heuristic() -> None:
    assert (
        assign_discovery_group(label="Solicitation Number", target_type="identifier")
        == "Solicitation Metadata"
    )
    assert (
        assign_discovery_group(label="Total Contract Value", target_type="amount")
        == "Pricing"
    )
    assert (
        assign_discovery_group(label="Hemoglobin", target_type="field")
        == "Document Fields"
    )


def test_value_types_follow_target_type() -> None:
    assert (
        infer_value_type(label="Effective Date", target_type="date") == "date"
    )
    assert (
        infer_value_type(label="Total Amount", target_type="amount")
        == "currency"
    )


def test_internal_paths_remain_rejected() -> None:
    assert is_internal_form_name("topmostSubform[0].Page1[0].PG11I[0]")
    assert not is_internal_form_name("Solicitation Number")
