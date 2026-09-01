from types import SimpleNamespace

from app.schemas.document_target import DocumentTarget
from app.services.generic_kv_scanner import is_plausible_kv_label
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

    assert result is not None
    assert result.value == "Jane A. Smith"


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
