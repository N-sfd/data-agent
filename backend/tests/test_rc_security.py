"""Release-candidate security checks — measurable, route-level.

Covers: RBAC on real routes, upload sanitization, CORS production shape,
audit actor/request context, log sanitization (no document text).
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.observability import _sanitize, log_event
from app.database.session import SessionLocal
from app.main import app
from app.models.document_metadata_field import DocumentMetadataField
from app.models.metadata_field_audit_log import MetadataFieldAuditLog
from app.services.file_upload import sanitize_display_filename
from sqlalchemy import select

client = TestClient(app)


def _pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "SECRET CLAUSE TEXT SHOULD NEVER LOG", fontsize=10)
    content = pdf.tobytes()
    pdf.close()
    return content


def test_production_cors_excludes_lan_debug_origins() -> None:
    settings = Settings(
        app_env="production",
        debug=False,
        frontend_url="https://data-agent-ca.vercel.app",
    )
    origins = settings.cors_origins
    assert "https://data-agent-ca.vercel.app" in origins
    assert "http://192.168.0.193:3000" not in origins
    assert "http://127.0.0.1:3001" not in origins


def test_path_traversal_filename_sanitized() -> None:
    cleaned = sanitize_display_filename(
        "../../etc/passwd\x00<script>.pdf", extension=".pdf"
    )
    assert ".." not in cleaned
    assert "/" not in cleaned
    assert "\\" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned.endswith(".pdf")
    assert "<" not in cleaned


def test_reject_executable_upload() -> None:
    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "malware.exe",
                b"MZ\x90\x00not-a-pdf",
                "application/octet-stream",
            )
        },
    )
    assert response.status_code in {400, 415, 422}
    # Must not create a stored document row for executables.
    assert "document_id" not in (response.json() if response.headers.get("content-type", "").startswith("application/json") else {})


def test_rbac_viewer_blocked_on_oracle_and_corrections() -> None:
    upload = client.post(
        "/api/documents/upload",
        files={"file": (f"rc-{uuid4()}.pdf", _pdf(), "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["document_id"]

    database = SessionLocal()
    try:
        database.add(
            DocumentMetadataField(
                document_id=document_id,
                field_group="Identifiers",
                field_key="contract_number",
                label="Contract Number",
                value="X",
                original_value="X",
                confidence=0.9,
                confidence_band="high",
                value_type="identifier",
                extraction_method="label_value",
                evidence_json={"page_number": 1, "source_text": "X", "source_reference": "p1"},
                verified=True,
                review_status="pending",
                extraction_source="target",
            )
        )
        database.commit()
    finally:
        database.close()

    headers = {"X-Actor-Id": "actor-viewer-default"}
    export = client.get(f"/api/documents/{document_id}/export", headers=headers)
    assert export.status_code == 403

    correction = client.post(
        f"/api/documents/{document_id}/targets/contract_number/corrections",
        headers=headers,
        json={"action": "verify", "original_value": "X"},
    )
    assert correction.status_code == 403

    oracle = client.get(
        f"/api/documents/{document_id}/oracle-payload",
        headers=headers,
    )
    assert oracle.status_code == 403


def test_audit_includes_actor_and_request_id() -> None:
    upload = client.post(
        "/api/documents/upload",
        files={"file": (f"rc-audit-{uuid4()}.pdf", _pdf(), "application/pdf")},
    )
    document_id = upload.json()["document_id"]
    database = SessionLocal()
    try:
        database.add(
            DocumentMetadataField(
                document_id=document_id,
                field_group="Financial",
                field_key="total_amount",
                label="Total Amount",
                value="$1",
                original_value="$1",
                confidence=0.9,
                confidence_band="high",
                value_type="currency",
                extraction_method="label_value",
                evidence_json={"page_number": 1, "source_text": "$1", "source_reference": "p1"},
                verified=True,
                review_status="pending",
                extraction_source="target",
            )
        )
        database.commit()
    finally:
        database.close()

    response = client.post(
        f"/api/documents/{document_id}/targets/total_amount/corrections",
        headers={"X-Actor-Id": "actor-reviewer-default"},
        json={
            "action": "edit",
            "original_value": "$1",
            "corrected_value": "$2",
            "changed_by": "RC Reviewer",
        },
    )
    assert response.status_code == 201
    assert response.headers.get("x-request-id")

    database = SessionLocal()
    try:
        row = database.scalar(
            select(MetadataFieldAuditLog).where(
                MetadataFieldAuditLog.document_id == document_id,
                MetadataFieldAuditLog.action == "edit",
            )
        )
        assert row is not None
        assert row.actor_id == "actor-reviewer-default"
        assert row.actor_role == "reviewer"
        assert row.request_id
        assert row.changed_by == "RC Reviewer"
    finally:
        database.close()


def test_log_sanitize_strips_document_text(caplog) -> None:
    clean = _sanitize(
        {
            "event": "extract",
            "source_text": "SECRET CLAUSE TEXT SHOULD NEVER LOG",
            "final_text": "full page body",
            "prompt": "system prompt leak",
            "page_number": 3,
            "document_id": "abc",
        }
    )
    assert "source_text" not in clean
    assert "final_text" not in clean
    assert "prompt" not in clean
    assert clean["page_number"] == 3
    assert clean["document_id"] == "abc"

    with caplog.at_level("INFO", logger="data_agent.obs"):
        log_event(
            "test_event",
            source_text="SECRET CLAUSE TEXT SHOULD NEVER LOG",
            page=1,
        )
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "SECRET CLAUSE" not in joined


def test_frontend_public_env_has_no_secret_keys() -> None:
    """Guardrail: client env example must only expose NEXT_PUBLIC_ / URLs."""

    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / "frontend" / ".env.example"
    text = example.read_text(encoding="utf-8")
    for banned in (
        "API_KEY",
        "SERVICE_ROLE",
        "SECRET",
        "PASSWORD",
        "PRIVATE_KEY",
    ):
        # Allow comments that mention keys conceptually; ban assignments.
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            assert banned not in stripped.upper() or stripped.upper().startswith(
                "NEXT_PUBLIC_"
            ), f"Suspicious frontend env line: {stripped}"


def test_rbac_enforced_blocks_spoofed_admin_on_export() -> None:
    upload = client.post(
        "/api/documents/upload",
        files={"file": (f"rc-spoof-{uuid4()}.pdf", _pdf(), "application/pdf")},
    )
    document_id = upload.json()["document_id"]
    enforced = get_settings().model_copy(update={"rbac_enforced": True})
    with patch("app.core.auth.get_settings", return_value=enforced):
        response = client.get(
            f"/api/documents/{document_id}/export",
            headers={"X-Actor-Id": "actor-admin-default"},
        )
    assert response.status_code == 401
