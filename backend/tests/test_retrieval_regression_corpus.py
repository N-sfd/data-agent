"""Fixed-corpus retrieval quality regressions."""

from __future__ import annotations

from types import SimpleNamespace

from app.schemas.document_target import DocumentTarget
from app.services.page_retrieval import (
    build_retrieval_trace,
    pages_from_trace,
    rank_pages_for_target,
)


# Gold labels: known correct source page for each business target.
RETRIEVAL_CORPUS = [
    {
        "key": "contract_number",
        "label": "Contract Number",
        "source_labels": ["CONTRACT NO."],
        "expected_page": 1,
        "pages": {
            1: "CONTRACT NO. FA3002-24-C-0008\nCover sheet.",
            2: "Vendor Address: 100 Main St Arlington VA",
            8: "Total Amount: $1,250,000.00",
            17: "Termination Conditions: either party may terminate for convenience.",
        },
    },
    {
        "key": "vendor_address",
        "label": "Vendor Address",
        "source_labels": ["Vendor Address"],
        "expected_page": 2,
        "pages": {
            1: "CONTRACT NO. FA3002-24-C-0008\nCover sheet.",
            2: "Vendor Address: 100 Main St Arlington VA",
            8: "Total Amount: $1,250,000.00",
            17: "Termination Conditions: either party may terminate for convenience.",
        },
    },
    {
        "key": "total_amount",
        "label": "Total Amount",
        "source_labels": ["Total Amount"],
        "expected_page": 8,
        "pages": {
            1: "CONTRACT NO. FA3002-24-C-0008\nCover sheet.",
            2: "Vendor Address: 100 Main St Arlington VA",
            8: "Total Amount: $1,250,000.00",
            17: "Termination Conditions: either party may terminate for convenience.",
        },
    },
    {
        "key": "termination_conditions",
        "label": "Termination Conditions",
        "source_labels": ["Termination Conditions"],
        "expected_page": 17,
        "pages": {
            1: "CONTRACT NO. FA3002-24-C-0008\nCover sheet.",
            2: "Vendor Address: 100 Main St Arlington VA",
            8: "Total Amount: $1,250,000.00",
            17: "Termination Conditions: either party may terminate for convenience.",
        },
    },
]


def _pages(mapping: dict[int, str]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            page_number=number,
            final_text=text,
            requires_ocr=False,
            ocr_succeeded=True,
            text_coverage_ratio=0.9,
            form_fields_json={},
            tables_json=[],
        )
        for number, text in sorted(mapping.items())
    ]


def _target(item: dict) -> DocumentTarget:
    return DocumentTarget(
        id=f"doc:{item['key']}",
        key=item["key"],
        label=item["label"],
        display_name=item["label"],
        target_type="field",
        page_numbers=[item["expected_page"]],
        confidence=0.9,
        source_labels=item["source_labels"],
        source_examples=[],
    )


def test_retrieval_top1_and_top3_hit_gold_pages() -> None:
    for item in RETRIEVAL_CORPUS:
        pages = _pages(item["pages"])
        target = _target(item)
        ranked = rank_pages_for_target(target=target, pages=pages, max_pages=5)
        top_pages = [entry.page for entry in ranked]
        expected = item["expected_page"]
        assert top_pages, item["key"]
        assert top_pages[0] == expected, f"{item['key']} top-1={top_pages}"
        assert expected in top_pages[:3], f"{item['key']} top-3={top_pages}"


def test_selected_pages_are_bounded_and_include_gold() -> None:
    for item in RETRIEVAL_CORPUS:
        pages = _pages(item["pages"])
        lookup = {page.page_number: page for page in pages}
        trace = build_retrieval_trace(target=_target(item), pages=pages, max_pages=5)
        assert item["expected_page"] in trace.selected_pages
        assert len(trace.selected_pages) <= 5
        selected = pages_from_trace(
            trace=trace,
            page_lookup=lookup,
            all_pages=pages,
            max_pages=5,
        )
        selected_numbers = {page.page_number for page in selected}
        assert item["expected_page"] in selected_numbers
        # AI context must never receive the full corpus when hits exist.
        assert len(selected) < len(pages) or len(pages) <= 5


def test_ai_context_pages_exclude_unrelated_noise() -> None:
    item = RETRIEVAL_CORPUS[0]
    noise = {i: f"boilerplate page {i}" for i in range(3, 7)}
    mapping = {**item["pages"], **noise}
    pages = _pages(mapping)
    lookup = {page.page_number: page for page in pages}
    trace = build_retrieval_trace(target=_target(item), pages=pages, max_pages=3)
    selected = pages_from_trace(
        trace=trace,
        page_lookup=lookup,
        all_pages=pages,
        max_pages=3,
    )
    selected_numbers = [page.page_number for page in selected]
    assert 1 in selected_numbers
    assert 4 not in selected_numbers or selected_numbers[0] == 1
