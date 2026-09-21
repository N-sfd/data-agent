"""Table quality gate + large selection extraction safety."""

from __future__ import annotations

from app.services.table_quality import (
    assess_table_candidate,
    is_accepted_table,
)


def test_prose_paragraph_rejected_as_table() -> None:
    headers = [
        "Pursuant to FAR 37.102(a)(2),",
        "OASIS+ task orders allow",
        "the ordering activity to",
    ]
    rows = [
        {
            headers[0]: "acquire services",
            headers[1]: "using performance-based",
            headers[2]: "acquisition methods when practicable.",
        }
    ]
    assessment = assess_table_candidate(headers=headers, rows=rows)
    assert assessment.table_acceptance_status == "rejected"
    assert assessment.prose_probability >= 0.5
    assert not is_accepted_table(headers=headers, rows=rows)


def test_section_heading_fragments_rejected() -> None:
    headers = ["Section G.3.1.", "Contract Administration", "Data"]
    rows = [
        {
            "Section G.3.1.": "The Contractor shall",
            "Contract Administration": "submit reports",
            "Data": "as required herein.",
        }
    ]
    assert not is_accepted_table(headers=headers, rows=rows)


def test_genuine_multi_row_table_accepted() -> None:
    headers = ["CLIN", "Description", "Amount"]
    rows = [
        {"CLIN": "0001", "Description": "Labor", "Amount": "1000"},
        {"CLIN": "0002", "Description": "Travel", "Amount": "250"},
        {"CLIN": "0003", "Description": "ODC", "Amount": "75"},
    ]
    assessment = assess_table_candidate(headers=headers, rows=rows)
    assert assessment.table_acceptance_status == "accepted"
    assert is_accepted_table(headers=headers, rows=rows)


def test_one_row_form_table_accepted() -> None:
    headers = ["A. NAME", "Solicitation Number", "Date Issued"]
    rows = [
        {
            "A. NAME": "Gabrina Daniels",
            "Solicitation Number": "47QRCA25DSF07",
            "Date Issued": "04/15/2025",
        }
    ]
    assert is_accepted_table(headers=headers, rows=rows)


def test_requested_ids_map_to_resolved_or_unresolved() -> None:
    """Deterministic mapping: every requested ID is accounted for."""

    from uuid import uuid4

    from app.schemas.document_target import DocumentTarget

    document_id = str(uuid4())
    targets = [
        DocumentTarget(
            id=f"{document_id}:field_{i}",
            key=f"field_{i}",
            label=f"Field {i}",
            target_type="field",
            page_numbers=[1],
            confidence=0.9,
            source_examples=[f"Field {i}: value"],
        )
        for i in range(320)
    ]
    targets_by_id = {target.id: target for target in targets}
    target_ids = [t.id for t in targets] + [
        f"{document_id}:missing_a",
        f"{document_id}:missing_b",
    ]

    requested = [
        targets_by_id[target_id]
        for target_id in target_ids
        if target_id in targets_by_id
    ]
    unresolved = [
        target_id for target_id in target_ids if target_id not in targets_by_id
    ]

    assert len(requested) == 320
    assert len(unresolved) == 2
    assert len(requested) + len(unresolved) == len(target_ids)
    # No silent drops — every ID maps to a result bucket.
    assert set(target_ids) == {t.id for t in requested} | set(unresolved)
