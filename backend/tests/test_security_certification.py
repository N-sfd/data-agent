"""Permission / security certification — Entra, RBAC enforcement, headers."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.entra import claims_to_actor_fields, map_entra_roles
from app.core.rbac import role_has_permission
from app.database.session import SessionLocal
from app.main import app
from app.models.actor import Actor
from app.services.actor_seed import DEFAULT_SERVICE_API_KEY

client = TestClient(app)


def _pdf() -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Contract Number: SEC-1", fontsize=10)
    content = pdf.tobytes()
    pdf.close()
    return content


def _upload() -> str:
    response = client.post(
        "/api/documents/upload",
        files={"file": (f"sec-{uuid4()}.pdf", _pdf(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def test_production_forces_rbac_enforced() -> None:
    settings = Settings(
        app_env="production",
        rbac_enforced=False,
        entra_tenant_id=None,
        entra_api_audience=None,
    )
    assert settings.effective_rbac_enforced is True


def test_entra_role_mapping_picks_highest() -> None:
    role = map_entra_roles({"roles": ["DataAgent.Viewer", "DataAgent.Reviewer"]})
    assert role == "reviewer"
    fields = claims_to_actor_fields(
        {
            "oid": "abc-123",
            "name": "Ada Reviewer",
            "preferred_username": "ada@contoso.com",
            "roles": ["DataAgent.Admin"],
        }
    )
    assert fields["id"] == "entra-abc-123"
    assert fields["role"] == "admin"
    assert fields["display_name"] == "Ada Reviewer"


def test_rbac_enforced_rejects_spoofed_actor_header() -> None:
    document_id = _upload()
    enforced = get_settings().model_copy(update={"rbac_enforced": True})

    with patch("app.core.auth.get_settings", return_value=enforced):
        response = client.get(
            f"/api/documents/{document_id}/export",
            headers={"X-Actor-Id": "actor-admin-default"},
        )
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]


def test_rbac_enforced_accepts_service_api_key() -> None:
    document_id = _upload()
    enforced = get_settings().model_copy(
        update={"rbac_enforced": True, "app_env": "development"}
    )

    with patch("app.core.auth.get_settings", return_value=enforced):
        # Also patch reviewed_export require_permission chain
        with patch("app.core.config.get_settings", return_value=enforced):
            response = client.get(
                f"/api/documents/{document_id}/export",
                headers={"Authorization": f"Bearer {DEFAULT_SERVICE_API_KEY}"},
            )
    assert response.status_code in {200, 404}
    # 404 only if no metadata fields — create none; export needs fields.
    # Upload alone has no fields → 404 is auth-success.
    assert response.status_code != 401
    assert response.status_code != 403


def test_entra_bearer_upserts_actor_and_authorizes() -> None:
    document_id = _upload()
    claims = {
        "oid": "oid-reviewer-99",
        "name": "Entra Reviewer",
        "preferred_username": "reviewer@contoso.com",
        "roles": ["DataAgent.Reviewer"],
    }
    entra_settings = get_settings().model_copy(
        update={
            "rbac_enforced": True,
            "entra_tenant_id": "tenant-test",
            "entra_api_audience": "api://data-agent",
        }
    )

    with (
        patch("app.core.auth.get_settings", return_value=entra_settings),
        patch(
            "app.core.auth.validate_entra_access_token",
            return_value=claims,
        ),
    ):
        # JWT-shaped bearer (three segments) triggers Entra path
        fake_jwt = "aaa.bbb.ccc"
        me = client.get(
            "/api/actors/me",
            headers={"Authorization": f"Bearer {fake_jwt}"},
        )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["id"] == "entra-oid-reviewer-99"
    assert body["role"] == "reviewer"
    assert "review.accept" in body["permissions"]
    assert not role_has_permission(body["role"], "oracle.send")

    database = SessionLocal()
    try:
        actor = database.get(Actor, "entra-oid-reviewer-99")
        assert actor is not None
        assert actor.display_name == "Entra Reviewer"
        assert actor.role == "reviewer"
    finally:
        database.close()


def test_viewer_entra_cannot_export_when_enforced() -> None:
    document_id = _upload()
    claims = {
        "oid": "oid-viewer-1",
        "name": "Read Only",
        "roles": ["DataAgent.Viewer"],
    }
    entra_settings = get_settings().model_copy(
        update={
            "rbac_enforced": True,
            "entra_tenant_id": "tenant-test",
            "entra_api_audience": "api://data-agent",
        }
    )
    with (
        patch("app.core.auth.get_settings", return_value=entra_settings),
        patch(
            "app.core.auth.validate_entra_access_token",
            return_value=claims,
        ),
    ):
        response = client.get(
            f"/api/documents/{document_id}/export",
            headers={"Authorization": "Bearer aaa.bbb.ccc"},
        )
    assert response.status_code == 403
    assert "export.read" in response.json()["detail"]


def test_security_headers_present() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert "strict-origin-when-cross-origin" in (
        response.headers.get("referrer-policy") or ""
    )


def test_ready_reports_auth_surface() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert "rbac_enforced" in body
    assert "entra_configured" in body
    assert "auth" in body["checks"]
    assert body["checks"]["auth"]["status"] in {"ok", "warn"}
