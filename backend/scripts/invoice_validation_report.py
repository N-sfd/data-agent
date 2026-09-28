"""Real-invoice validation report — runs each file through the real local
pipeline (upload → native text / OCR / DOM → extraction → profile
resolution → staging workbook) and writes one Markdown report per file:

    Document → detected family → selected profile → each business tab
    (value, Verified / Needs Review / Missing, reasons, source evidence
    with page) → arithmetic and QA checks.

Everything stays on this machine: it uses the local database configured
for the backend and writes reports OUTSIDE the repo by default (real
invoices must never be committed).

Usage (from backend/):
    python scripts/invoice_validation_report.py path/to/a.pdf path/to/b.jpg
    python scripts/invoice_validation_report.py --out C:/reports invoices/*.pdf
    python scripts/invoice_validation_report.py --truth truth.json invoices/*.pdf

With --truth, every checked value is scored Correct/Incorrect x
Verified/Needs Review (plus Missing); "Incorrect + Verified" is the
release blocker.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.services.v3_orchestrator import run_and_persist_v3_extraction  # noqa: E402
from app.staging.resolver import resolve_and_persist_profile  # noqa: E402

MIME = {
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}
BUSINESS_TABS = (
    "invoice_summary",
    "supplier",
    "customer",
    "reference",
    "invoice_lines",
    "taxes_charges",
    "totals",
)
STATUS_MARK = {"Verified": "Verified", "Needs Review": "**Needs Review**", "Missing": "_Missing_"}

client = TestClient(app)


def process(path: Path) -> dict:
    mime = MIME.get(path.suffix.lower())
    if mime is None:
        raise SystemExit(f"Unsupported file type: {path.name}")
    # Always a fresh document: reusing an earlier upload would report its
    # cached structure/profile from whatever code version processed it.
    upload = client.post(
        "/api/documents/upload",
        params={"allow_duplicate": "true"},
        files={"file": (path.name, path.read_bytes(), mime)},
    )
    if upload.status_code != 201:
        raise SystemExit(f"Upload failed for {path.name}: {upload.status_code} {upload.text[:300]}")
    document_id = upload.json()["document_id"]
    pages = client.post(f"/api/documents/{document_id}/extract-pages", json={"run_ocr": True})
    if pages.status_code != 200:
        raise SystemExit(f"Page extraction failed for {path.name}: {pages.text[:300]}")
    database = SessionLocal()
    try:
        document = database.get(Document, document_id)
        page_rows = list(database.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id)))
        run_and_persist_v3_extraction(database=database, document=document, pages=page_rows)
        resolve_and_persist_profile(database, document)
    finally:
        database.close()
    workbook = client.get(f"/api/documents/{document_id}/staging-workbook")
    if workbook.status_code != 200:
        raise SystemExit(f"Workbook failed for {path.name}: {workbook.text[:300]}")
    return workbook.json()


def _md(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " / ")


def _evidence(cell: dict) -> str:
    provenance = cell.get("provenance") or {}
    where = []
    if provenance.get("source_page"):
        where.append(f"p{provenance['source_page']}")
    locator = provenance.get("source_locator") or {}
    if locator.get("dom_path"):
        where.append(locator["dom_path"].rsplit("/", 2)[-2] + "/" + locator["dom_path"].rsplit("/", 1)[-1])
    if provenance.get("extraction_method"):
        where.append(provenance["extraction_method"])
    evidence = provenance.get("highlight_text") or provenance.get("evidence_text") or ""
    evidence = " ".join(evidence.split())[:90]
    return (" · ".join(where) + (f" — “{evidence}”" if evidence else "")) or "—"


def render(path: Path, wb: dict) -> str:
    meta = wb["processing_metadata"]
    profile = wb["profile"]
    qa = wb["qa_summary"]
    out = [
        f"# {path.name}",
        "",
        "| Stage | Result |",
        "|---|---|",
        f"| Document | {_md(path.name)} ({_md(meta.get('source_type'))}, {meta.get('page_count')} page(s)) |",
        f"| Detected family | {_md(meta.get('document_family_label') or meta.get('document_family'))} |",
        f"| Selected profile | {profile['profile_id']}@{profile['profile_version']} |",
        f"| Outcome | {_md(wb['outcome'].get('status'))} — {_md(wb['outcome'].get('title'))} |",
        f"| Cell states | {qa['verified']} Verified · {qa['needs_review']} Needs Review · {qa['missing']} Missing |",
        "",
    ]
    if meta.get("resolution_reasons"):
        out += ["Profile selection: " + "; ".join(meta["resolution_reasons"]), ""]

    for dataset in wb["datasets"]:
        if dataset["dataset_id"] not in BUSINESS_TABS:
            continue
        out.append(f"## {dataset['display_name']} ({len(dataset['records'])} record(s))")
        out.append("")
        if not dataset["records"]:
            out += ["_No records._", ""]
            continue
        if dataset["cardinality"] == "single":
            out += ["| Field | Value | State | Source evidence | Reasons |", "|---|---|---|---|---|"]
            for record in dataset["records"]:
                for column in dataset["columns"]:
                    cell = record["cells"].get(column["canonical_field"])
                    if cell is None or (cell.get("value") in (None, "") and cell.get("review_status") != "Missing"):
                        continue
                    out.append(
                        f"| {_md(column['display_label'])} | {_md(cell.get('value'))} | "
                        f"{STATUS_MARK.get(cell.get('review_status'), _md(cell.get('review_status')))} | "
                        f"{_md(_evidence(cell))} | {_md('; '.join(cell.get('review_reasons') or []))} |"
                    )
        else:
            columns = [
                c for c in dataset["columns"]
                if any(r["cells"].get(c["canonical_field"], {}).get("value") not in (None, "") for r in dataset["records"])
                and not c["canonical_field"].endswith(("source_table", "other_values"))
            ]
            out.append("| # | " + " | ".join(_md(c["display_label"]) for c in columns) + " | State | Evidence |")
            out.append("|---|" + "---|" * len(columns) + "---|---|")
            for index, record in enumerate(dataset["records"], start=1):
                cells = [record["cells"].get(c["canonical_field"], {}) for c in columns]
                flagged = [
                    f"{c['display_label']}: {'; '.join(cell.get('review_reasons') or [cell.get('review_status')])}"
                    for c, cell in zip(columns, cells)
                    if cell.get("review_status") in ("Needs Review", "Missing")
                ]
                anchor = next((cell for cell in reversed(cells) if cell.get("provenance")), {})
                out.append(
                    f"| {index} | " + " | ".join(_md(cell.get("value")) for cell in cells)
                    + f" | {_md('; '.join(flagged)) if flagged else 'Verified'} | {_md(_evidence(anchor))} |"
                )
        out.append("")

    out += ["## Arithmetic & QA checks", "", "| Check | Result | Details |", "|---|---|---|"]
    qa_dataset = next((d for d in wb["datasets"] if d["dataset_id"] == "qa_review"), None)
    for record in (qa_dataset or {}).get("records", []):
        cells = record["cells"]
        out.append(
            f"| {_md(cells.get('qa.check', {}).get('value'))} | {_md(cells.get('qa.result', {}).get('value'))} | "
            f"{_md(cells.get('qa.details', {}).get('value'))} |"
        )
    out += [
        "",
        "## Reviewer verdict (fill in)",
        "",
        "- Confidently wrong values (Verified but incorrect): ",
        "- Correct values flagged Needs Review: ",
        "- Values present on the invoice but Missing: ",
        "- Line items: expected __ / extracted __ / correct __",
        "",
    ]
    return "\n".join(out)


# --- ground truth ------------------------------------------------------------------
#
# --truth points at a JSON file keyed by filename. Scalar keys below are
# optional (null = "not on this invoice", so any extracted value is wrong);
# line_amounts / line_item_numbers are per-line lists in document order.

TRUTH_SCALARS = {
    "invoice_number": ("invoice_summary", "invoice.invoice_number", "text"),
    "invoice_date": ("invoice_summary", "invoice.invoice_date", "date"),
    "due_date": ("invoice_summary", "invoice.due_date", "date"),
    "currency": ("invoice_summary", "invoice.currency", "text"),
    "payment_terms": ("invoice_summary", "invoice.payment_terms", "text"),
    "po_number": ("reference", "invoice.reference.po_number", "text"),
    "supplier_name": ("supplier", "invoice.supplier.name", "text"),
    "customer_name": ("customer", "invoice.customer.name", "text"),
    "subtotal": ("totals", "invoice.total.subtotal", "money"),
    "tax": ("totals", "invoice.total.tax", "money"),
    "freight": ("totals", "invoice.total.freight", "money"),
    "discount": ("totals", "invoice.total.discount", "signless"),
    "invoice_total": ("totals", "invoice.total.invoice_amount", "money"),
    "amount_due": ("totals", "invoice.total.amount_due", "money"),
}
CATEGORIES = (
    "Correct + Verified",
    "Correct + Needs Review",
    "Incorrect + Needs Review",
    "Incorrect + Verified",
    "Missing",
)
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d %B %Y", "%B %d, %Y", "%d-%b-%Y", "%d.%m.%Y")


def _number(value) -> float | None:
    text = re.sub(r"[^\d.\-]", "", str(value or "").replace("−", "-"))
    try:
        return float(text) if text not in ("", "-", ".") else None
    except ValueError:
        return None


def _date(value) -> str | None:
    text = " ".join(str(value or "").split())
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalized(value) -> str:
    return " ".join(str(value).split()).strip(" .,;:").lower()


def _matches(extracted, expected, kind: str) -> bool:
    if kind in ("money", "signless"):
        a, b = _number(extracted), _number(expected)
        if a is None or b is None:
            return False
        if kind == "signless":  # the label ("Discount") carries the sign
            a, b = abs(a), abs(b)
        return abs(a - b) < 0.005
    if kind == "date":
        a = _date(extracted)
        return a is not None and a == _date(expected)
    return _normalized(extracted) == _normalized(expected)


def _single(wb: dict, dataset_id: str) -> dict:
    dataset = next((d for d in wb["datasets"] if d["dataset_id"] == dataset_id), None)
    return dataset["records"][0]["cells"] if dataset and dataset["records"] else {}


def _line_records(wb: dict) -> list[dict]:
    return next((d for d in wb["datasets"] if d["dataset_id"] == "invoice_lines"), {"records": []})["records"]


def score(wb: dict, truth: dict) -> list[dict]:
    """One row per checked value: field, expected, extracted, state, category."""

    rows: list[dict] = []

    def judge(field: str, cell: dict | None, expected, kind: str) -> None:
        value = (cell or {}).get("value")
        state = (cell or {}).get("review_status") or "Missing"
        present = value not in (None, "")
        verified = state == "Verified"
        if expected is None:
            if not present:
                return  # correctly absent
            # The invoice has no such value, yet one was produced.
            category = "Incorrect + Verified" if verified else "Incorrect + Needs Review"
        elif not present:
            category = "Missing"
        else:
            correct = _matches(value, expected, kind)
            category = (
                ("Correct + Verified" if verified else "Correct + Needs Review")
                if correct
                else ("Incorrect + Verified" if verified else "Incorrect + Needs Review")
            )
        rows.append({"field": field, "expected": expected, "extracted": value, "state": state, "category": category})

    for key, (dataset_id, canonical, kind) in TRUTH_SCALARS.items():
        if key in truth:
            judge(key, _single(wb, dataset_id).get(canonical), truth[key], kind)

    lines = _line_records(wb)
    amounts = truth.get("line_amounts") or []
    items = truth.get("line_item_numbers") or []
    for index in range(max(len(lines), len(amounts))):
        cells = lines[index]["cells"] if index < len(lines) else {}
        if index < len(amounts):
            judge(f"line {index + 1} amount", cells.get("invoice.line.amount"), amounts[index], "money")
        elif cells:
            judge(f"line {index + 1} (extra row)", cells.get("invoice.line.amount"), None, "money")
        if index < len(items):
            judge(f"line {index + 1} item", cells.get("invoice.line.item_number"), items[index], "text")
    return rows


def render_truth(truth: dict, rows: list[dict], wb: dict) -> str:
    counts = {c: sum(1 for r in rows if r["category"] == c) for c in CATEGORIES}
    blockers = [r for r in rows if r["category"] == "Incorrect + Verified"]
    expected_lines = truth.get("line_count", len(truth.get("line_amounts") or []))
    out = ["## Ground-truth check", "", "| Category | Count |", "|---|---|"]
    for category in CATEGORIES:
        label = f"**{category} ← RELEASE BLOCKER**" if category == "Incorrect + Verified" else category
        out.append(f"| {label} | {counts[category]} |")
    out += [
        "",
        f"Line count: expected {expected_lines}, extracted {len(_line_records(wb))}.",
        "",
        "**Verdict: "
        + ("FAIL — at least one Verified value is wrong." if blockers else "PASS — no Verified value is wrong.")
        + "**",
        "",
    ]
    flagged = [r for r in rows if r["category"] != "Correct + Verified"]
    if flagged:
        out += ["| Field | Expected | Extracted | State | Category |", "|---|---|---|---|---|"]
        for r in flagged:
            out.append(
                f"| {_md(r['field'])} | {_md(r['expected'])} | {_md(r['extracted'])} | "
                f"{_md(r['state'])} | {r['category']} |"
            )
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "invoice_validation_reports")
    parser.add_argument("--truth", type=Path, help="JSON ground truth keyed by filename")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    truths = json.loads(args.truth.read_text(encoding="utf-8")) if args.truth else {}
    summary = [
        "| File | Family | Profile | Verified | Needs Review | Missing | Arithmetic | "
        + " | ".join(CATEGORIES)
        + " | Verdict |",
        "|---|---|---|---|---|---|---|" + "---|" * len(CATEGORIES) + "---|",
    ]
    for path in args.files:
        wb = process(path)
        report = args.out / f"{path.stem}.md"
        text = render(path, wb)
        truth = truths.get(path.name)
        rows = score(wb, truth) if truth else []
        if truth:
            text = text.replace(
                "## Arithmetic & QA checks", render_truth(truth, rows, wb) + "\n## Arithmetic & QA checks", 1
            )
        report.write_text(text, encoding="utf-8")
        qa_dataset = next((d for d in wb["datasets"] if d["dataset_id"] == "qa_review"), {"records": []})
        arithmetic = [
            r["cells"]["qa.result"]["value"] for r in qa_dataset["records"]
            if str(r["cells"]["qa.check"]["value"]).startswith("Arithmetic")
        ]
        qa = wb["qa_summary"]
        summary.append(
            f"| {_md(path.name)} | {_md(wb['processing_metadata'].get('document_family'))} | "
            f"{wb['profile']['profile_id']}@{wb['profile']['profile_version']} | {qa['verified']} | "
            f"{qa['needs_review']} | {qa['missing']} | {', '.join(arithmetic) or 'not checked'} | "
            + (
                " | ".join(str(sum(1 for r in rows if r["category"] == c)) for c in CATEGORIES)
                + (" | **FAIL** |" if any(r["category"] == "Incorrect + Verified" for r in rows) else " | PASS |")
                if truth
                else " | ".join("—" for _ in CATEGORIES) + " | no truth |"
            )
        )
        print(f"wrote {report}")
    (args.out / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
