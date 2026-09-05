import time
from unittest.mock import patch
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_provider import DisabledAIProvider

client = TestClient(app)


def create_pdf(lines: list[str]) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()

    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=9)
        y += 14

    content = pdf.tobytes()
    pdf.close()

    return content


def upload_and_discover(lines: list[str], filename: str) -> str:
    upload = client.post(
        "/api/documents/upload",
        files={"file": (filename, create_pdf(lines), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]

    extraction = client.post(
        f"/api/documents/{document_id}/extract-pages",
        json={
            "run_ocr": False,
            "page_start": None,
            "page_end": None,
            "force_reprocess": False,
        },
    )
    assert extraction.status_code == 200, extraction.text

    with patch(
        "app.api.universal_extraction.create_ai_provider",
        return_value=DisabledAIProvider(),
    ):
        discover = client.post(
            f"/api/documents/{document_id}/discover-schema"
        )
    assert discover.status_code == 200, discover.text

    return document_id


def test_add_custom_target_requires_prior_discovery() -> None:
    upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                f"no-discovery-{uuid4()}.pdf",
                create_pdf(["Some text."]),
                "application/pdf",
            )
        },
    )
    document_id = upload.json()["document_id"]

    response = client.post(
        f"/api/documents/{document_id}/targets/custom",
        json={"label": "Renewal Option Date"},
    )
    assert response.status_code == 409, response.text


def test_add_rename_and_delete_custom_target() -> None:
    document_id = upload_and_discover(
        ["Contract Number: W912DR-26-C-0042"],
        f"custom-target-{uuid4()}.pdf",
    )

    create_response = client.post(
        f"/api/documents/{document_id}/targets/custom",
        json={"label": "Renewal Option Date"},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["label"] == "Renewal Option Date"
    assert created["source"] == "custom"
    target_key = created["key"]

    targets = client.get(f"/api/documents/{document_id}/targets").json()
    assert any(t["key"] == target_key for t in targets["targets"])

    rename_response = client.patch(
        f"/api/documents/{document_id}/targets/custom/{target_key}",
        json={"label": "Renewal Option Deadline"},
    )
    assert rename_response.status_code == 200, rename_response.text
    assert rename_response.json()["label"] == "Renewal Option Deadline"

    delete_response = client.delete(
        f"/api/documents/{document_id}/targets/custom/{target_key}"
    )
    assert delete_response.status_code == 204

    targets_after = client.get(
        f"/api/documents/{document_id}/targets"
    ).json()
    assert not any(
        t["key"] == target_key for t in targets_after["targets"]
    )


def test_cannot_rename_or_delete_a_detected_target() -> None:
    document_id = upload_and_discover(
        ["Contract Number: W912DR-26-C-0042"],
        f"protect-detected-{uuid4()}.pdf",
    )

    targets = client.get(f"/api/documents/{document_id}/targets").json()
    detected = next(
        t for t in targets["targets"] if t["source"] == "detected"
    )

    rename_response = client.patch(
        f"/api/documents/{document_id}/targets/custom/{detected['key']}",
        json={"label": "Hijacked label"},
    )
    assert rename_response.status_code == 404

    delete_response = client.delete(
        f"/api/documents/{document_id}/targets/custom/{detected['key']}"
    )
    assert delete_response.status_code == 404


def test_adding_a_custom_target_does_not_erase_discovered_targets() -> None:
    document_id = upload_and_discover(
        ["Contract Number: W912DR-26-C-0042"],
        f"preserve-discovery-{uuid4()}.pdf",
    )

    before = client.get(f"/api/documents/{document_id}/targets").json()
    before_keys = {t["key"] for t in before["targets"]}
    assert before_keys

    client.post(
        f"/api/documents/{document_id}/targets/custom",
        json={"label": "Renewal Option Date"},
    )

    after = client.get(f"/api/documents/{document_id}/targets").json()
    after_keys = {t["key"] for t in after["targets"]}

    assert before_keys.issubset(after_keys)


def test_extraction_job_handles_over_100_selected_fields() -> None:
    """A user selecting 100+ fields must see one action succeed — the
    job runner batches internally rather than the request being capped
    or the caller having to split it into multiple calls."""

    document_id = upload_and_discover(
        ["Contract Number: W912DR-26-C-0042"],
        f"bulk-custom-fields-{uuid4()}.pdf",
    )

    target_ids: list[str] = []
    for index in range(118):
        response = client.post(
            f"/api/documents/{document_id}/targets/custom",
            json={"label": f"Custom Field {index}"},
        )
        assert response.status_code == 201, response.text
        target_ids.append(response.json()["id"])

    assert len(target_ids) == 118

    start_response = client.post(
        f"/api/documents/{document_id}/jobs/extract",
        json={"target_ids": target_ids, "use_ai_fallback": False},
    )
    assert start_response.status_code == 202, start_response.text
    job_id = start_response.json()["id"]

    job = None
    for _ in range(50):
        job = client.get(f"/v1/jobs/{job_id}").json()
        if job["status"] in ("complete", "failed"):
            break
        time.sleep(0.1)

    assert job is not None
    assert job["status"] == "complete", job
    assert job["result"] is not None
    resolved_or_unresolved = len(job["result"]["scalars"]) + len(
        job["result"]["unresolved_targets"]
    )
    assert resolved_or_unresolved == 118
