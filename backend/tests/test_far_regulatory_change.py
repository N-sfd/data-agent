"""far_regulatory_change@1 — a Federal Register FAR final rule (FAC 2026-01,
FAR Case 2025-007, Trade Agreements Thresholds): Rule Summary + one FAR Rule
Data table of the rule, its preamble, thresholds and amendatory changes.

The real rule PDF is a public Federal Register document kept in
reference/regression; the end-to-end tests skip when it is absent."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.far.final_rule import _changes_from, _paragraphs, far_number, join_lines
from app.main import app
from app.models.document import Document
from app.staging.preparation import prepare_staging

client = TestClient(app)
RULE_PDF = Path(__file__).resolve().parents[2] / "reference" / "regression" / "far_final_rule_2026-04912.pdf"
D = "rule.data."


def test_change_sentences():
    assert _changes_from("In section 22.1503 amend paragraph (b)(2) by removing ‘‘$102,280’’ and adding ‘‘$105,767’’ in its place.") == [
        (["$102,280"], ["$105,767"])
    ]
    assert _changes_from(
        "Removing from paragraphs (c)(3) and (d)(3) ‘‘$6,708,000’’ and ‘‘$13,296,489’’ and adding ‘‘$6,683,000’’ and "
        "‘‘$13,749,689’’ in their places, respectively."
    ) == [(["$6,708,000", "$13,296,489"], ["$6,683,000", "$13,749,689"])]
    assert _paragraphs("Removing from paragraph (c)(1)(xxi)(C) ‘‘$102,280’’") == "(c)(1)(xxi)(C)"
    assert _paragraphs("Removing from the introductory text of paragraphs (a) and (c) ‘‘x’’") == "(a) and (c)"
    assert far_number("52.204–8") == "52.204-8"
    # A line-end hyphen before a lowercase word joins as printed.
    assert join_lines(["El Salvador, Guate-", "mala, Honduras"]) == "El Salvador, Guate-mala, Honduras"


@pytest.fixture(scope="module")
def rule() -> dict:
    if not RULE_PDF.exists():
        pytest.skip("reference Federal Register rule PDF not present")
    content = RULE_PDF.read_bytes() + b"\n%" + uuid4().hex.encode()
    upload = client.post("/api/documents/upload", files={"file": ("2026-04912.pdf", content, "application/pdf")})
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]
    assert client.post(f"/api/documents/{document_id}/extract-pages", json={"run_ocr": False}).status_code == 200
    database = SessionLocal()
    try:
        assert prepare_staging(database, database.get(Document, document_id)).record.profile_id == "far_regulatory_change"
    finally:
        database.close()
    workbook = client.get(f"/api/documents/{document_id}/staging-workbook").json()
    datasets = {d["dataset_id"]: d for d in workbook["datasets"]}
    rows = [
        {c["canonical_field"].removeprefix(D): c["value"] for c in record["cells"].values()} | {"_status": record["record_status"]}
        for record in datasets["far_rule_data"]["records"]
    ]
    summary = {c["display_label"]: c["value"] for c in datasets["rule_summary"]["records"][0]["cells"].values()}
    return {"id": document_id, "workbook": workbook, "rows": rows, "summary": summary}


def test_two_tabs_and_a_dynamic_label(rule):
    profile = rule["workbook"]["profile"]
    assert profile["display_name"] == "FAR Final Rule"
    assert [v["label"] for v in profile["views"]] == ["Rule Summary", "FAR Rule Data"]


def test_rule_summary(rule):
    s = rule["summary"]
    assert s["Document Label"] == "FAR Final Rule"
    assert s["Heading"] == "Federal Acquisition Regulation — Trade Agreements Thresholds"
    assert s["Reference"] == "FAC 2026-01 | FAR Case 2025-007"
    assert s["Effective Date"] == "March 13, 2026"
    assert s["CFR Parts Amended"] == "48 CFR Parts 22, 25, and 52"
    assert s["FR Document Number"] == "2026-04912"
    assert s["Federal Register Citation"] == "91 FR 12488–12491"
    assert s["RIN"] == "9000-AO80"
    # The FAC introduction and the compliance guide in the same PDF are
    # companions, never mixed into the rule.
    assert "2026-04911" in s["Companion Documents"] and "2026-04913" in s["Companion Documents"]


def test_amendments_previous_and_new_values(rule):
    changes = {(r["far_reference"], r["previous_value"]): r for r in rule["rows"] if r["action"] == "Replace value"}
    assert changes[("22.1503(b)(2)", "$102,280")]["new_value"] == "$105,767"
    assert changes[("25.202(c)", "$6,708,000")]["new_value"] == "$6,683,000"
    # "…, respectively": each value pair is its own change.
    assert changes[("25.1102(c)(3) and (d)(3)", "$13,296,489")]["new_value"] == "$13,749,689"
    clause = changes[("52.222-19(a)(2)", "$102,280")]
    assert clause["record_type"] == "Clause Amendment"
    assert clause["clause_number"] == "52.222-19" and clause["clause_title"] == "Child Labor—Cooperation with Authorities and Remedies"
    assert clause["regulation_part"].startswith("PART 52—SOLICITATION PROVISIONS AND CONTRACT CLAUSES")
    assert all(r["effective_date"] == "March 13, 2026" and r["fac_number"] == "2026-01" for r in changes.values())


def test_clause_date_revisions(rule):
    revisions = {r["clause_number"]: r for r in rule["rows"] if r["action"] == "Revise date"}
    assert set(revisions) == {"52.204-8", "52.212-5", "52.213-4", "52.222-19"}
    assert revisions["52.204-8"]["record_type"] == "Provision Date Revision"
    assert revisions["52.212-5"]["record_type"] == "Clause Date Revision"
    assert all(r["revision_date"] == "MAR 2026" and r["new_value"] == "(MAR 2026)" for r in revisions.values())


def test_threshold_tables(rule):
    thresholds = [r for r in rule["rows"] if r["record_type"] == "Trade Agreement Threshold"]
    assert len(thresholds) == 28  # the USTR table in the preamble and FAR 25.402(b) Table 1
    table_1 = [r for r in thresholds if r["far_reference"] == "25.402(b)"]
    assert len(table_1) == 14 and all(r["section"] == "Amendment 4" for r in table_1)
    wto = table_1[0]
    assert (wto["trade_agreement"], wto["supply_threshold"], wto["service_threshold"], wto["construction_threshold"]) == (
        "WTO GPA", "$174,000", "$174,000", "$6,683,000",
    )
    by_name = {r["trade_agreement"]: r for r in table_1}
    assert by_name["FTAs — Bahrain FTA"]["construction_threshold"] == "13,749,689"
    assert "FTAs — CAFTA–DR (Costa Rica, Dominican Republic, El Salvador, Guate-mala, Honduras, and Nicaragua)" in by_name
    assert by_name["USMCA — Mexico"]["supply_threshold"] == "105,767"
    assert by_name["Oman FTA"]["supply_threshold"] == "174,000"  # not a USMCA member
    # A dot-leader cell is "no threshold", never a value.
    israel = by_name["Israeli Trade Act"]
    assert (israel["supply_threshold"], israel["service_threshold"], israel["construction_threshold"]) == ("50,000", None, None)


def test_preamble_sections_in_order_and_everything_verified(rule):
    sections = [r["section"] for r in rule["rows"] if r["record_type"] == "Preamble Section"]
    assert sections[0] == "I. Background" and sections[-1] == "X. Paperwork Reduction Act" and len(sections) == 10
    assert all(r["_status"] == "Verified" for r in rule["rows"])
    assert all(r["source_page"] and r["source_reference"].startswith("91 FR ") for r in rule["rows"])


def test_exports(rule):
    base = f"/api/documents/{rule['id']}/staging-workbook"
    rows = list(csv.reader(io.StringIO(client.get(f"{base}/datasets/far_rule_data.csv").content.decode("utf-8-sig"))))
    assert rows[0][:5] == ["Section", "Record Type", "FAR Reference", "Title / Subject", "Action / Change"]
    assert len(rows) - 1 == len(rule["rows"])
    assert client.get(f"{base}/export.xlsx").status_code == 200


def test_far_part_files_are_not_rules():
    """A FAR Part (current regulation) never resolves to the change profile."""

    from tests.test_far_part_52 import _prepare, far_pdf

    content = far_pdf() + b"\n%" + uuid4().hex.encode()
    upload = client.post("/api/documents/upload", files={"file": ("part.pdf", content, "application/pdf")})
    document_id = upload.json()["document_id"]
    client.post(f"/api/documents/{document_id}/extract-pages", json={"run_ocr": False})
    assert _prepare(document_id)["profile_id"] == "far_part_52"
