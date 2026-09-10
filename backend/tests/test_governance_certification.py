"""Governance certification suite.

Certifies durable review state across routing reasons, Accept/Edit/Reject,
append-only audit, reopen identity, and re-extraction that must not silently
overwrite human decisions.
"""

from __future__ import annotations

from uuid import uuid4

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.main import app
from app.models.document_metadata_field import DocumentMetadataField
from app.models.metadata_field_audit_log import MetadataFieldAuditLog
from app.schemas.document_target import ScalarTargetResult
from app.schemas.extraction_intelligence import (
    ConfidenceDetail,
    ConfidenceSignals,
    RetrievalTrace,
    ValidationCheck,
    ValidationResult,
)
from app.services.review_routing import (
    REASON_AI_ESCALATION,
    REASON_AMBIGUOUS,
    REASON_EXTRACTION_DIFFERS,
    REASON_LOW_CONFIDENCE,
    REASON_NOT_SOURCE_GROUNDED,
    REASON_VALIDATION_FAILED,
    decide_review_for_scalar,
)
from app.services.target_result_store import (
    load_persisted_extract_results,
    persist_target_extraction_results,
)

client = TestClient(app)


def _pdf(marker: str = "W912DR-26-C-0042") -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), f"Contract Number: {marker}", fontsize=10)
    page.insert_text((72, 92), "Total Amount: $120,000", fontsize=10)
    content = pdf.tobytes()
    pdf.close()
    return content


def _upload() -> str:
    response = client.post(
        "/api/documents/upload",
        files={"file": (f"gov-{uuid4()}.pdf", _pdf(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def _scalar(**overrides) -> ScalarTargetResult:
    defaults = {
        "target": "Total Amount",
        "normalized_key": "total_amount",
        "value": "$120,000",
        "page": 1,
        "confidence": 0.92,
        "confidence_band": "high",
        "verified": True,
        "extraction_method": "label_value",
        "display_method": "Native",
        "evidence": {
            "page_number": 1,
            "source_text": "Total Amount: $120,000",
            "source_reference": "page 1",
        },
        "validation": ValidationResult(
            status="passed",
            checks=[ValidationCheck(type="format", status="passed")],
            warnings=[],
        ),
        "confidence_detail": ConfidenceDetail(
            score=0.92,
            band="high",
            signals=ConfidenceSignals(
                exact_label_match=True,
                label_proximity="strong",
                native_text=True,
                format_validation=True,
                source_grounded=True,
                corroborating_occurrences=1,
                ambiguity=False,
                ai_fallback=False,
            ),
        ),
        "retrieval": RetrievalTrace(
            target_key="total_amount",
            selected_pages=[1],
            deterministic_status="resolved",
            ai_fallback_required=False,
        ),
    }
    defaults.update(overrides)
    return ScalarTargetResult(**defaults)


def _seed_field(
    database: Session,
    document_id: str,
    *,
    key: str = "total_amount",
    value: str = "$120,000",
    review_status: str = "pending",
    evidence: dict | None = None,
    confidence: float = 0.92,
    band: str = "high",
    verified: bool = True,
) -> DocumentMetadataField:
    field = DocumentMetadataField(
        document_id=document_id,
        field_group="Financial",
        field_key=key,
        label="Total Amount",
        value=value,
        original_value=value,
        confidence=confidence,
        confidence_band=band,
        value_type="currency",
        extraction_method="label_value",
        evidence_json=evidence
        or {
            "page_number": 1,
            "source_text": f"Total Amount: {value}",
            "source_reference": "page 1",
            "machine_value": value,
            "review_decision": {
                "status": "ready_to_accept",
                "priority": "high",
                "reasons": [],
            },
        },
        verified=verified,
        review_status=review_status,
        extraction_source="target",
    )
    database.add(field)
    database.commit()
    database.refresh(field)
    return field


# --- Routing matrix (durable initial status) ---------------------------------


def test_high_confidence_auto_accept_off_stays_pending() -> None:
    decision = decide_review_for_scalar(_scalar(), auto_accept_high_confidence=False)
    assert decision["review_status"] == "pending"
    assert decision["status"] == "ready_to_accept"
    assert decision["reasons"] == []


def test_low_confidence_pending_with_reason() -> None:
    decision = decide_review_for_scalar(
        _scalar(confidence=0.4, confidence_band="low")
    )
    assert decision["review_status"] == "pending"
    assert REASON_LOW_CONFIDENCE in decision["reasons"]


def test_validation_failure_pending_with_reason() -> None:
    decision = decide_review_for_scalar(
        _scalar(
            validation=ValidationResult(
                status="failed",
                checks=[ValidationCheck(type="format", status="failed")],
                warnings=["bad format"],
            )
        )
    )
    assert decision["review_status"] == "pending"
    assert REASON_VALIDATION_FAILED in decision["reasons"]


def test_not_source_grounded_pending_with_reason() -> None:
    decision = decide_review_for_scalar(_scalar(verified=False))
    assert decision["review_status"] == "pending"
    assert REASON_NOT_SOURCE_GROUNDED in decision["reasons"]


def test_ambiguous_candidates_pending_with_reason() -> None:
    decision = decide_review_for_scalar(
        _scalar(
            retrieval=RetrievalTrace(
                target_key="total_amount",
                selected_pages=[1, 2],
                deterministic_status="ambiguous",
                ai_fallback_required=False,
            )
        )
    )
    assert decision["review_status"] == "pending"
    assert REASON_AMBIGUOUS in decision["reasons"]


def test_ai_escalation_reason_retained() -> None:
    decision = decide_review_for_scalar(
        _scalar(
            extraction_method="ai",
            retrieval=RetrievalTrace(
                target_key="total_amount",
                selected_pages=[1],
                deterministic_status="unresolved",
                ai_fallback_required=True,
            ),
        )
    )
    assert decision["review_status"] == "pending"
    assert REASON_AI_ESCALATION in decision["reasons"]


# --- Accept / Edit / Reject + append-only audit -----------------------------


def test_accept_sets_accepted_and_audit() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(database, document_id)
    finally:
        database.close()

    response = client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={"action": "verify", "original_value": "$120,000"},
    )
    assert response.status_code == 201, response.text

    database = SessionLocal()
    try:
        field = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.field_key == "total_amount",
            )
        )
        assert field is not None
        assert field.review_status == "accepted"

        audit = database.scalars(
            select(MetadataFieldAuditLog)
            .where(
                MetadataFieldAuditLog.document_id == document_id,
                MetadataFieldAuditLog.field_key == "total_amount",
            )
            .order_by(MetadataFieldAuditLog.id.asc())
        ).all()
        assert len(audit) == 1
        assert audit[0].action == "accept"
        assert audit[0].previous_status == "pending"
        assert audit[0].new_status == "accepted"
        assert audit[0].reason == "Reviewer accept"
        assert audit[0].request_id  # middleware sets X-Request-ID
    finally:
        database.close()


def test_edit_sets_edited_with_old_new_and_audit() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(database, document_id)
    finally:
        database.close()

    response = client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={
            "action": "edit",
            "original_value": "$120,000",
            "corrected_value": "$125,000",
        },
    )
    assert response.status_code == 201, response.text

    database = SessionLocal()
    try:
        field = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.field_key == "total_amount",
            )
        )
        assert field is not None
        assert field.review_status == "edited"
        assert field.value == "$125,000"
        evidence = field.evidence_json or {}
        assert evidence.get("machine_value") == "$120,000"
        assert evidence.get("reviewed_value") == "$125,000"

        audit = database.scalar(
            select(MetadataFieldAuditLog).where(
                MetadataFieldAuditLog.document_id == document_id,
                MetadataFieldAuditLog.action == "edit",
            )
        )
        assert audit is not None
        assert audit.previous_value == "$120,000"
        assert audit.new_value == "$125,000"
        assert audit.previous_status == "pending"
        assert audit.new_status == "edited"
        assert audit.reason == "Reviewer correction"
    finally:
        database.close()


def test_reject_sets_rejected_and_audit() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(database, document_id)
    finally:
        database.close()

    response = client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={"action": "reject", "original_value": "$120,000"},
    )
    assert response.status_code == 201, response.text

    database = SessionLocal()
    try:
        field = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.field_key == "total_amount",
            )
        )
        assert field is not None
        assert field.review_status == "rejected"

        audit = database.scalar(
            select(MetadataFieldAuditLog).where(
                MetadataFieldAuditLog.document_id == document_id,
                MetadataFieldAuditLog.action == "reject",
            )
        )
        assert audit is not None
        assert audit.previous_status == "pending"
        assert audit.new_status == "rejected"
    finally:
        database.close()


def test_audit_log_is_append_only_across_decisions() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(database, document_id)
    finally:
        database.close()

    client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={"action": "verify", "original_value": "$120,000"},
    )
    client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={
            "action": "edit",
            "original_value": "$120,000",
            "corrected_value": "$125,000",
        },
    )
    client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={"action": "reject", "original_value": "$125,000"},
    )

    database = SessionLocal()
    try:
        rows = database.scalars(
            select(MetadataFieldAuditLog)
            .where(MetadataFieldAuditLog.document_id == document_id)
            .order_by(MetadataFieldAuditLog.id.asc())
        ).all()
        assert [row.action for row in rows] == ["accept", "edit", "reject"]
        assert [row.new_status for row in rows] == [
            "accepted",
            "edited",
            "rejected",
        ]
    finally:
        database.close()


# --- Reopen identity --------------------------------------------------------


def test_reopen_preserves_status_reasons_and_audit() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(
            database,
            document_id,
            evidence={
                "page_number": 1,
                "source_text": "Total Amount: $120,000",
                "source_reference": "page 1",
                "review_decision": {
                    "status": "needs_review",
                    "priority": "low",
                    "reasons": [REASON_LOW_CONFIDENCE],
                },
            },
            confidence=0.4,
            band="low",
        )
    finally:
        database.close()

    client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={
            "action": "edit",
            "original_value": "$120,000",
            "corrected_value": "$125,000",
        },
    )

    database = SessionLocal()
    try:
        loaded = load_persisted_extract_results(
            database=database, document_id=document_id
        )
        assert loaded is not None
        assert len(loaded.scalars) == 1
        scalar = loaded.scalars[0]
        assert scalar.value == "$125,000"

        field = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.field_key == "total_amount",
            )
        )
        assert field is not None
        assert field.review_status == "edited"
        decision = (field.evidence_json or {}).get("review_decision") or {}
        assert REASON_LOW_CONFIDENCE in (decision.get("reasons") or [])

        audits = database.scalars(
            select(MetadataFieldAuditLog).where(
                MetadataFieldAuditLog.document_id == document_id
            )
        ).all()
        assert len(audits) == 1
        assert audits[0].action == "edit"
    finally:
        database.close()

    # HTTP reopen path
    reopen = client.get(f"/api/documents/{document_id}/extract-results")
    assert reopen.status_code == 200, reopen.text
    body = reopen.json()
    assert body["scalars"][0]["value"] == "$125,000"


# --- Re-extraction must not destroy human decisions -------------------------


def test_reextract_preserves_edited_value_and_flags_diff() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(database, document_id)
    finally:
        database.close()

    client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={
            "action": "edit",
            "original_value": "$120,000",
            "corrected_value": "$125,000",
        },
    )

    database = SessionLocal()
    try:
        persist_target_extraction_results(
            database=database,
            document_id=document_id,
            scalars=[_scalar(value="$127,000")],
            tables=[],
        )
        field = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.field_key == "total_amount",
            )
        )
        assert field is not None
        # Authoritative reviewed value must survive.
        assert field.value == "$125,000"
        assert field.review_status == "pending"
        evidence = field.evidence_json or {}
        assert evidence.get("machine_value") == "$127,000"
        assert evidence.get("reviewed_value") == "$125,000"
        reasons = (evidence.get("review_decision") or {}).get("reasons") or []
        assert REASON_EXTRACTION_DIFFERS in reasons

        # Prior edit audit still present (append-only; re-extract does not rewrite).
        audits = database.scalars(
            select(MetadataFieldAuditLog).where(
                MetadataFieldAuditLog.document_id == document_id
            )
        ).all()
        assert any(row.action == "edit" for row in audits)
    finally:
        database.close()


def test_reextract_preserves_accepted_when_machine_unchanged() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(database, document_id)
    finally:
        database.close()

    client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={"action": "verify", "original_value": "$120,000"},
    )

    database = SessionLocal()
    try:
        persist_target_extraction_results(
            database=database,
            document_id=document_id,
            scalars=[_scalar(value="$120,000")],
            tables=[],
        )
        field = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.field_key == "total_amount",
            )
        )
        assert field is not None
        assert field.value == "$120,000"
        assert field.review_status == "accepted"
    finally:
        database.close()


def test_reextract_accepted_diff_requires_review_without_overwrite() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(database, document_id)
    finally:
        database.close()

    client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        json={"action": "verify", "original_value": "$120,000"},
    )

    database = SessionLocal()
    try:
        persist_target_extraction_results(
            database=database,
            document_id=document_id,
            scalars=[_scalar(value="$130,000")],
            tables=[],
        )
        field = database.scalar(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id,
                DocumentMetadataField.field_key == "total_amount",
            )
        )
        assert field is not None
        assert field.value == "$120,000"
        assert field.review_status == "pending"
        reasons = (
            (field.evidence_json or {}).get("review_decision") or {}
        ).get("reasons") or []
        assert REASON_EXTRACTION_DIFFERS in reasons
    finally:
        database.close()


def test_review_queue_focus_href_includes_field_key() -> None:
    document_id = _upload()
    database = SessionLocal()
    try:
        _seed_field(
            database,
            document_id,
            confidence=0.4,
            band="low",
            verified=False,
            evidence={
                "page_number": 1,
                "source_text": "Total Amount: $120,000",
                "source_reference": "page 1",
                "review_decision": {
                    "status": "needs_review",
                    "priority": "low",
                    "reasons": [REASON_LOW_CONFIDENCE, REASON_NOT_SOURCE_GROUNDED],
                },
            },
        )
    finally:
        database.close()

    response = client.get("/api/dashboard/review-queue/fields")
    assert response.status_code == 200
    match = next(
        (
            item
            for item in response.json()
            if item["document_id"] == document_id
            and item["field_key"] == "total_amount"
        ),
        None,
    )
    assert match is not None
    assert match["review_href"] == (
        f"/extraction/new?documentId={document_id}&focus=total_amount"
    )
