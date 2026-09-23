"""V3 ground-truth quality gate — automated source-grounding audit.

For every canonical V3 record on the regression contract, reports dataset,
business key, source page, evidence, routing/classification reason, QA
status, and a validation result (does the evidence text actually appear on
the claimed page). Flags: missing evidence, page mismatch, duplicate
canonical identity within a dataset, and suspicious cross-dataset reuse of
the same evidence/page across dataset families that should be mutually
exclusive (CLIN vs Funding vs Contract Summary vs Attachment vs Clause).

This is a regression artifact (developer diagnostic), not a V3 export
sheet — run it, read the printed report, it does not modify data.

Usage: python backend/scripts/v3_source_grounding_audit.py
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.document_attachment import DocumentAttachment  # noqa: E402
from app.models.document_clause_reference import DocumentClauseReference  # noqa: E402
from app.models.document_contract_summary import DocumentContractSummary  # noqa: E402
from app.models.document_funding_line import DocumentFundingLine  # noqa: E402
from app.models.document_line_item import DocumentLineItem  # noqa: E402
from app.models.document_metadata_field import DocumentMetadataField  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.models.document_performance_period import DocumentPerformancePeriod  # noqa: E402

PDF_NAME_LIKE = "Contract_47QRCA%"


def _page_text(pages_by_number: dict[int, str], page_number: int | None) -> str:
    if not page_number:
        return ""
    return pages_by_number.get(page_number, "")


import re as _re

_PUNCT_RE = _re.compile(r"[^a-z0-9]+")


def _word_set(text: str) -> set[str]:
    return {w for w in _PUNCT_RE.sub(" ", text.lower()).split() if len(w) >= 3}


def _evidence_check(evidence: str | None, page_text: str) -> str:
    if not evidence or not evidence.strip():
        return "MISSING_EVIDENCE"
    if not page_text.strip():
        return "PAGE_MISMATCH"
    # Word-overlap ratio rather than exact substring: evidence is often
    # captured via regex/label-value formatting ("LABEL -> VALUE") or
    # loses a comma/newline during storage normalization, which breaks a
    # strict substring check without the grounding actually being wrong.
    # A real, on-page quote should still share most of its distinctive
    # (3+ letter) words with that page's text; a wrong page shares almost
    # none.
    evidence_words = _word_set(evidence[:200])
    if not evidence_words:
        return "MISSING_EVIDENCE"
    page_words = _word_set(page_text)
    overlap = evidence_words & page_words
    ratio = len(overlap) / len(evidence_words)
    if ratio >= 0.7:
        return "OK"
    return "PAGE_MISMATCH"


def main() -> None:
    database = SessionLocal()
    document = database.scalars(
        select(Document).where(Document.original_filename.like(PDF_NAME_LIKE))
    ).first()
    if document is None:
        print("Regression document not found.")
        return

    pages = list(
        database.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        )
    )
    pages_by_number = {p.page_number: (p.final_text or "") for p in pages}

    report_rows: list[dict] = []
    evidence_registry: dict[str, list[tuple[str, str]]] = defaultdict(list)  # evidence_key -> [(dataset, business_key)]

    def add_row(
        dataset: str,
        business_key: str,
        source_page: int | None,
        evidence: str | None,
        reason: str,
        qa_status: str | None,
    ) -> None:
        check = _evidence_check(evidence, _page_text(pages_by_number, source_page))
        report_rows.append(
            {
                "dataset": dataset,
                "key": business_key,
                "page": source_page,
                "evidence": (evidence or "")[:90],
                "reason": reason,
                "qa_status": qa_status,
                "validation": check,
            }
        )
        if evidence and evidence.strip():
            norm = " ".join(evidence.split())[:60].strip().lower()
            if norm:
                evidence_registry[norm].append((dataset, business_key))

    # --- Contract Summary ---
    cs = database.scalars(
        select(DocumentContractSummary).where(
            DocumentContractSummary.document_id == document.id
        )
    ).first()
    if cs is not None:
        for field_name in (
            "contract_number", "solicitation_rfp", "contract_vehicle", "agency_office",
            "contractor", "award_date", "ceiling_max_aggregate", "minimum_guarantee",
            "base_period", "options", "max_duration", "task_order_range", "naics",
            "size_standard",
        ):
            value = getattr(cs, field_name)
            prov = (cs.field_provenance_json or {}).get(
                {
                    "contract_number": "Contract Number",
                    "solicitation_rfp": "Solicitation / RFP",
                    "contract_vehicle": "Contract Vehicle",
                    "agency_office": "Agency / Office",
                    "contractor": "Contractor",
                    "award_date": "Award Date",
                    "ceiling_max_aggregate": "Ceiling / Max Aggregate",
                    "minimum_guarantee": "Minimum Guarantee",
                    "base_period": "Base Period",
                    "options": "Options",
                    "max_duration": "Max Duration",
                    "task_order_range": "Task Order Range",
                    "naics": "NAICS",
                    "size_standard": "Size Standard",
                }.get(field_name, ""),
                {},
            )
            page = prov.get("page") or cs.source_page
            evidence = prov.get("evidence") or cs.evidence
            add_row(
                "Contract Summary",
                field_name,
                page,
                evidence,
                "field_provenance" if prov else "summary_level_provenance",
                cs.qa_status if value else "NOT_FOUND",
            )

    # --- CLINs ---
    clins = list(
        database.scalars(
            select(DocumentLineItem).where(DocumentLineItem.document_id == document.id)
        )
    )
    for row in clins:
        ev = row.evidence_json or {}
        add_row(
            "CLINs",
            row.clin or f"row-{row.row_index}",
            ev.get("page_number"),
            ev.get("source_text"),
            ",".join(ev.get("reason_codes") or []),
            row.qa_status,
        )

    # --- Funding ---
    funding = list(
        database.scalars(
            select(DocumentFundingLine).where(DocumentFundingLine.document_id == document.id)
        )
    )
    for row in funding:
        ev = row.evidence_json or {}
        add_row(
            "Funding",
            f"{row.funding_level}/{row.clin}/{row.amount}",
            ev.get("page_number"),
            ev.get("source_text"),
            ",".join(ev.get("reason_codes") or []),
            row.qa_status,
        )

    # --- Performance Delivery ---
    perf = list(
        database.scalars(
            select(DocumentPerformancePeriod).where(
                DocumentPerformancePeriod.document_id == document.id
            )
        )
    )
    for row in perf:
        ev = row.evidence_json or {}
        add_row(
            "Performance Delivery",
            f"{row.record_type}#{row.row_index}",
            ev.get("page_number"),
            ev.get("source_text"),
            ",".join(ev.get("reason_codes") or []),
            row.qa_status,
        )

    # --- Attachments ---
    attachments = list(
        database.scalars(
            select(DocumentAttachment).where(DocumentAttachment.document_id == document.id)
        )
    )
    for row in attachments:
        ev = row.evidence_json or {}
        add_row(
            "Attachments",
            row.attachment_reference,
            ev.get("page_number"),
            ev.get("source_text"),
            ",".join(ev.get("reason_codes") or []),
            row.qa_status,
        )

    # --- Clauses / FAR References / DFARS (one shared table) ---
    clause_refs = list(
        database.scalars(
            select(DocumentClauseReference).where(
                DocumentClauseReference.document_id == document.id
            )
        )
    )
    classification_basis_counts: Counter[str] = Counter()
    for row in clause_refs:
        ev = row.evidence_json or {}
        basis = ev.get("classification_basis", "UNKNOWN")
        classification_basis_counts[(row.clause_family, row.citation_context, basis)] += 1
        if row.clause_family in ("FAR", "GSAR") and row.citation_context == "listing":
            dataset = "Clauses"
        elif row.clause_family == "DFARS":
            dataset = "DFARS"
        else:
            dataset = "FAR References"
        add_row(
            dataset,
            f"{row.clause_family} {row.clause_number}",
            ev.get("page_number"),
            ev.get("source_text"),
            f"basis={basis},far_master={row.far_master_match_status}",
            row.qa_status,
        )

    # --- All Fields ---
    all_fields = list(
        database.scalars(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document.id,
                DocumentMetadataField.extraction_source == "v3",
            )
        )
    )
    for row in all_fields:
        ev = row.evidence_json or {}
        add_row(
            "All Fields",
            row.label,
            ev.get("page_number"),
            ev.get("source_text"),
            ",".join(ev.get("reason_codes") or []),
            ev.get("qa_status"),
        )

    # === Report ===
    print(f"Document: {document.original_filename} ({document.id})")
    print(f"Total canonical records audited: {len(report_rows)}\n")

    print("=" * 120)
    print("FULL RECORD-LEVEL REPORT")
    print("=" * 120)
    print(f"{'DATASET':<22}{'KEY':<28}{'PAGE':>5}  {'VALIDATION':<15}{'QA STATUS':<12}REASON")
    for r in report_rows:
        print(
            f"{r['dataset']:<22}{str(r['key'])[:26]:<28}{str(r['page'] or ''):>5}  "
            f"{r['validation']:<15}{str(r['qa_status'] or ''):<12}{r['reason'][:60]}"
        )

    print("\n" + "=" * 120)
    print("VALIDATION SUMMARY BY DATASET")
    print("=" * 120)
    by_dataset: dict[str, Counter[str]] = defaultdict(Counter)
    for r in report_rows:
        by_dataset[r["dataset"]][r["validation"]] += 1
    for dataset, counts in by_dataset.items():
        total = sum(counts.values())
        print(f"  {dataset:<22} total={total:<5} " + " ".join(f"{k}={v}" for k, v in counts.items()))

    print("\n" + "=" * 120)
    print("CLAUSE/FAR-REFERENCE/DFARS CLASSIFICATION BASIS BREAKDOWN")
    print("=" * 120)
    for (family, context, basis), count in sorted(classification_basis_counts.items()):
        print(f"  {family:<6} {context:<10} {basis:<28} {count}")

    print("\n" + "=" * 120)
    print("DUPLICATE CANONICAL IDENTITY CHECK (within each dataset)")
    print("=" * 120)
    keys_by_dataset: dict[str, Counter[str]] = defaultdict(Counter)
    for r in report_rows:
        keys_by_dataset[r["dataset"]][str(r["key"])] += 1
    any_dupes = False
    for dataset, counts in keys_by_dataset.items():
        dupes = {k: v for k, v in counts.items() if v > 1}
        if dupes:
            any_dupes = True
            print(f"  {dataset}: {dupes}")
    if not any_dupes:
        print("  none found")

    print("\n" + "=" * 120)
    print("SUSPICIOUS CROSS-DATASET EVIDENCE REUSE")
    print("=" * 120)
    # Same underlying source text feeding more than one dataset FAMILY that
    # should be mutually exclusive (CLIN vs Funding vs Contract Summary vs
    # Attachment vs Clause/FAR-Reference/DFARS). All Fields legitimately
    # overlaps with Contract Summary by design (the cross-cutting index),
    # so that pair is excluded from the flag.
    mutually_exclusive_families = {"CLINs", "Funding", "Attachments", "Clauses", "FAR References", "DFARS"}
    any_reuse = False
    for evidence_key, usages in evidence_registry.items():
        datasets_used = {d for d, _ in usages}
        flagged = datasets_used & mutually_exclusive_families
        if len(flagged) > 1:
            any_reuse = True
            print(f"  evidence={evidence_key!r} -> {usages}")
    if not any_reuse:
        print("  none found")

    database.close()


if __name__ == "__main__":
    main()
