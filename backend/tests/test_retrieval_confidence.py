from types import SimpleNamespace

from app.schemas.document_target import DocumentTarget
from app.schemas.extraction_intelligence import ConfidenceSignals
from app.services.confidence_engine import explain_confidence
from app.services.page_retrieval import (
    build_retrieval_trace,
    rank_pages_for_target,
    select_pages_for_target,
)
from app.services.result_validation import build_validation_result


def _page(number: int, text: str, *, ocr: bool = False, tables=None) -> SimpleNamespace:
    return SimpleNamespace(
        page_number=number,
        final_text=text,
        requires_ocr=ocr,
        ocr_succeeded=ocr,
        text_coverage_ratio=0.9,
        form_fields_json={},
        tables_json=tables or [],
    )


def _target(**overrides) -> DocumentTarget:
    defaults = {
        "id": "doc:contract_number",
        "key": "contract_number",
        "label": "Contract Number",
        "target_type": "identifier",
        "page_numbers": [2],
        "confidence": 0.9,
        "source_examples": [],
        "source_labels": ["CONTRACT NO."],
        "display_name": "Contract Number",
    }
    defaults.update(overrides)
    return DocumentTarget(**defaults)


def test_rank_pages_prefers_discovery_and_label_hits() -> None:
    pages = [
        _page(1, "Cover sheet and unrelated preamble."),
        _page(2, "CONTRACT NO. FA300224C0008 appears here."),
        _page(47, "Termination may occur upon written notice."),
        _page(231, "More boilerplate without the contract number."),
    ]
    ranked = rank_pages_for_target(
        target=_target(page_numbers=[2]),
        pages=pages,
        max_pages=3,
    )
    assert ranked[0].page == 2
    assert ranked[0].score >= ranked[-1].score
    assert ranked[0].score > 0.5


def test_retrieval_trace_is_inspectable() -> None:
    pages = [
        _page(6, "General definitions."),
        _page(17, "Termination Conditions: either party may terminate for convenience."),
        _page(42, "See also termination for default on notice."),
    ]
    target = _target(
        key="termination_conditions",
        label="Termination Conditions",
        page_numbers=[17],
        source_labels=["Termination Conditions"],
    )
    trace = build_retrieval_trace(target=target, pages=pages, max_pages=5)
    assert trace.target_key == "termination_conditions"
    assert trace.candidate_pages[0].page == 17
    assert 17 in trace.selected_pages
    assert len(trace.selected_pages) <= 5
    assert trace.deterministic_status == "not_attempted"
    assert trace.ai_fallback_required is False
    payload = trace.model_dump()
    assert "candidate_pages" in payload
    assert "selected_pages" in payload


def test_select_pages_never_returns_full_document_when_hits_exist() -> None:
    pages = [_page(i, f"noise page {i}") for i in range(1, 21)]
    pages[4] = _page(5, "Payment Terms: Net 30 and invoice details.")
    target = _target(
        key="payment_terms",
        label="Payment Terms",
        page_numbers=[],
        source_labels=["Payment Terms"],
    )
    lookup = {page.page_number: page for page in pages}
    selected = select_pages_for_target(
        target=target,
        pages=pages,
        page_lookup=lookup,
        max_pages=5,
    )
    assert len(selected) <= 5
    assert any(page.page_number == 5 for page in selected)


def test_explain_confidence_uses_structured_signals() -> None:
    page = _page(1, "native text", ocr=False)
    explained = explain_confidence(
        method="source_evidence",
        page=page,
        source_grounded=True,
        validation_passed=True,
        exact_label_match=True,
    )
    assert explained.band == "high"
    assert explained.score >= 0.85
    assert isinstance(explained.signals, ConfidenceSignals)
    assert explained.signals.exact_label_match is True
    assert explained.signals.label_proximity == "strong"
    assert explained.signals.native_text is True
    assert explained.signals.format_validation is True
    assert explained.signals.source_grounded is True
    assert explained.signals.ai_fallback is False
    assert explained.signals.ambiguity is False
    payload = explained.model_dump()
    assert set(payload["signals"].keys()) == {
        "exact_label_match",
        "label_proximity",
        "native_text",
        "format_validation",
        "source_grounded",
        "corroborating_occurrences",
        "ambiguity",
        "ai_fallback",
    }


def test_ai_method_starts_lower_than_native_evidence() -> None:
    page = _page(1, "text")
    native = explain_confidence(method="source_evidence", page=page)
    ai = explain_confidence(method="ai", page=page, match_exactness=0.7)
    assert native.score > ai.score
    assert ai.signals.ai_fallback is True


def test_validation_result_is_first_class() -> None:
    result = build_validation_result(
        value="FA300224C0008",
        value_type="identifier",
        source_text="Contract Number: FA300224C0008",
        page_text="Contract Number: FA300224C0008 appears here.",
    )
    assert result.status == "passed"
    assert [check.type for check in result.checks] == [
        "data_type",
        "format",
        "source_presence",
    ]
    assert all(check.status == "passed" for check in result.checks)
    assert result.warnings == []

    failed = build_validation_result(
        value="not-an-email",
        value_type="email",
        source_text="Contact: not-an-email",
        page_text="Contact: not-an-email",
    )
    assert failed.status == "failed"
    assert any(check.type == "data_type" and check.status == "failed" for check in failed.checks)
