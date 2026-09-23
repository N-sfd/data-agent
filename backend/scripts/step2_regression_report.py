"""Step 2 regression report: same regression contract as Step 1
(reference/regression/Contract_47QRCA25DSF07 (2).pdf), but now classifying
at LINE granularity (app/services/line_model.py) instead of block
granularity, with semantic validation (contract_summary_fields.py) and
CLIN/Funding deduplication applied - end to end, in memory, zero database
writes.

Usage: python backend/scripts/step2_regression_report.py
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import fitz  # noqa: E402

from app.services.candidate_router import (  # noqa: E402
    deduplicate_clin_funding_overlap,
    route_clause_citations,
    route_clin_rows,
    route_form_cell_associations,
    route_page_regions,
)
from app.services.clause_citation_scanner import scan_pages_for_clause_citations  # noqa: E402
from app.services.clin_block_detector import parse_clin_rows  # noqa: E402
from app.services.contract_summary_fields import (  # noqa: E402
    FIELD_KEY_TO_V3_COLUMN,
    STEP2_EVALUATED_SUMMARY_FIELDS,
    match_label,
)
from app.services.form_cell_associator import associate_form_cells  # noqa: E402
from app.services.generic_table_extractor import extract_page_tables  # noqa: E402
from app.services.line_model import lines_from_fitz_page  # noqa: E402
from app.services.structure_classifier import (  # noqa: E402
    build_document_context,
    classify_page_regions,
)

PDF_PATH = BACKEND_ROOT.parent / "reference" / "regression" / "Contract_47QRCA25DSF07 (2).pdf"

NEGATIVE_REGRESSION_EXAMPLES = [
    ("Amount", "$0.00"),
    ("NAICS", "Codes"),
    ("Solicitation Number", "whether or not Contractors"),
    ("Adm 4800", None),
    ("B.8", "1 CONUS Standardized Labor Categories"),
    ("C.1", "1 North American Industry Classification System"),
    ("F.4", "1 Deliverable and Reporting Requirements"),
    ("F.5", None),
    ("FAR", "TITLE and DATE"),
]

CONTRACT_SUMMARY_TARGETS = [
    ("Contract Number", "contract_number"),
    ("Solicitation Number", "solicitation_number"),
    ("Award Date", "award_date"),
    ("Date Issued", "date_issued"),
    ("UEID", "ueid"),
    ("Contracting Officer Name", "contracting_officer_name"),
    ("Contracting Officer Phone", "telephone"),
    ("Contracting Officer Email", "email"),
]


def main() -> None:
    started = time.perf_counter()
    doc = fitz.open(str(PDF_PATH))
    page_count = doc.page_count
    print(f"Loaded {PDF_PATH.name}: {page_count} pages (LINE-granularity pipeline)")

    all_lines_by_page: dict[int, list] = {}
    all_tables_by_page: dict[int, list] = {}
    page_heights: dict[int, float] = {}
    context_input: list[tuple[int, list, float]] = []

    for page_index in range(page_count):
        page = doc[page_index]
        page_number = page_index + 1
        lines = lines_from_fitz_page(page=page, page_number=page_number)
        all_lines_by_page[page_number] = lines
        page_heights[page_number] = float(page.rect.height)
        context_input.append((page_number, lines, float(page.rect.height)))

        try:
            tables = extract_page_tables(str(PDF_PATH), page_number)
        except Exception:
            tables = []
        all_tables_by_page[page_number] = tables

    extraction_elapsed = time.perf_counter() - started
    print(f"Line extraction (dict-mode, no OCR) + tables: {extraction_elapsed:.1f}s")

    classify_started = time.perf_counter()
    doc_context = build_document_context(pages=context_input)

    regions_by_page = {}
    all_text_by_page: dict[int, str] = {}
    for page_number in range(1, page_count + 1):
        regions_by_page[page_number] = classify_page_regions(
            page_number=page_number,
            blocks=all_lines_by_page[page_number],
            tables=all_tables_by_page[page_number],
            page_height=page_heights[page_number],
            doc_context=doc_context,
        )
        all_text_by_page[page_number] = "\n".join(
            l.text for l in all_lines_by_page[page_number]
        )
    classify_elapsed = time.perf_counter() - classify_started

    pseudo_pages = [
        SimpleNamespace(
            page_number=page_number,
            final_text=all_text_by_page[page_number],
            tables_json=all_tables_by_page[page_number],
        )
        for page_number in range(1, page_count + 1)
    ]

    citations = scan_pages_for_clause_citations(
        pages=pseudo_pages, regions_by_page=regions_by_page
    )
    clin_rows = []
    for page in pseudo_pages:
        clin_rows.extend(parse_clin_rows(page=page))

    candidates = []
    for page_number in range(1, page_count + 1):
        # Prefer line-level form-cell ownership for numbered gov-form fields.
        form_cells = associate_form_cells(lines=all_lines_by_page[page_number])
        candidates.extend(route_form_cell_associations(form_cells))
        # Structural regions only — skip FORM_FIELD_* to avoid double-pairing
        # after form-cell ownership already claimed those lines.
        structural_only = [
            r
            for r in regions_by_page[page_number]
            if r.region_type not in ("FORM_FIELD_LABEL", "FORM_FIELD_VALUE")
        ]
        candidates.extend(route_page_regions(structural_only))
    candidates.extend(route_clause_citations(citations))
    candidates.extend(route_clin_rows(clin_rows))
    candidates = deduplicate_clin_funding_overlap(candidates)

    total_elapsed = time.perf_counter() - started
    print(
        f"Classification+routing: {classify_elapsed:.1f}s | "
        f"total: {total_elapsed:.1f}s for {page_count} pages -> "
        f"{total_elapsed / page_count * 1000:.0f}ms/page"
    )
    print(f"Total lines: {sum(len(v) for v in all_lines_by_page.values())}")
    print(f"Total classified candidates: {len(candidates)}")
    print(f"Clause citations: {len(citations)} | CLIN rows: {len(clin_rows)}")

    print("\n" + "=" * 100)
    print("A. STEP 1 NEGATIVE-REGRESSION CHECK (must remain green)")
    print("=" * 100)
    all_green = True
    for old_field, old_value in NEGATIVE_REGRESSION_EXAMPLES:
        bad_survivors = [
            c
            for c in candidates
            if c.category in ("CONTRACT_SUMMARY", "GENERAL_ACCEPTED_FIELD")
            and old_field.lower() in (c.evidence or "").lower()
            and (old_value is None or old_value.lower() in (c.value or "").lower())
        ]
        status = "PASS (excluded)" if not bad_survivors else "FAIL (reappeared as business field!)"
        if bad_survivors:
            all_green = False
        print(f"  {old_field!r} -> {old_value!r}: {status}")
    print(f"\nOverall negative regression: {'ALL GREEN' if all_green else 'REGRESSION DETECTED'}")

    print("\n" + "=" * 100)
    print("B. CONTRACT SUMMARY REGRESSION TABLE")
    print("=" * 100)
    accepted = [
        c
        for c in candidates
        if c.category in ("CONTRACT_SUMMARY", "GENERAL_ACCEPTED_FIELD") and c.value
    ]
    by_field_key: dict[str, object] = {}

    def _field_key_of(candidate: object) -> str | None:
        for reason in getattr(candidate, "reason_codes", []) or []:
            if isinstance(reason, str) and reason.startswith("field_key_"):
                return reason[len("field_key_") :]
        return match_label(getattr(candidate, "label", None) or "")

    for c in accepted:
        key = _field_key_of(c)
        if not key:
            continue
        if key not in by_field_key:
            by_field_key[key] = c
        # Offeror name is the V3 Contractor column when present.
        if key == "offeror_name" and "contractor_name" not in by_field_key:
            by_field_key["contractor_name"] = c

    print(
        f"{'V3 / gate field':<28} {'raw label':<28} {'value':<28} "
        f"{'page':>4} {'status':<14} confidence"
    )
    for display, field_key in CONTRACT_SUMMARY_TARGETS:
        c = by_field_key.get(field_key)
        v3_col = FIELD_KEY_TO_V3_COLUMN.get(field_key, "(evaluated; not V3 Summary col)")
        if c is None:
            print(
                f"  {display:<26} {'—':<28} {'NOT FOUND':<28} "
                f"{'—':>4} {'Needs Review':<14} —"
            )
            continue
        print(
            f"  {display:<26} {(c.label or '')[:26]:<28} {(c.value or '')[:26]:<28} "
            f"{c.source_page:>4} {'Passed':<14} {c.confidence:.2f}"
            f"  [{v3_col}]"
        )

    print("\nAll STEP2_EVALUATED_SUMMARY_FIELDS present:")
    for field_key in STEP2_EVALUATED_SUMMARY_FIELDS:
        c = by_field_key.get(field_key)
        status = f"value={c.value!r} page={c.source_page}" if c else "Not Found / Needs Review"
        print(f"  {field_key}: {status}")

    print("\nFull V3 Contract Summary columns (manifest §11):")
    v3_columns = [
        "Contract Number",
        "Solicitation / RFP",
        "Contract Vehicle",
        "Agency / Office",
        "Contractor",
        "Award Date",
        "Ceiling / Max Aggregate",
        "Minimum Guarantee",
        "Base Period",
        "Options",
        "Max Duration",
        "Task Order Range",
        "NAICS",
        "Size Standard",
        "Source File",
        "Source Page",
        "Evidence",
        "QA Status",
    ]
    reverse_v3 = {col: key for key, col in FIELD_KEY_TO_V3_COLUMN.items()}
    for col in v3_columns:
        if col in ("Source File", "Source Page", "Evidence", "QA Status"):
            print(f"  {col}: (provenance — assigned at persistence, not extracted)")
            continue
        key = reverse_v3.get(col)
        c = by_field_key.get(key) if key else None
        if c is None and col == "Contractor":
            c = by_field_key.get("contractor_name") or by_field_key.get("offeror_name")
        if c is None:
            print(f"  {col}: Not Found / Needs Review")
        else:
            print(
                f"  {col}: value={c.value!r} label={c.label!r} "
                f"page={c.source_page} conf={c.confidence:.2f}"
            )

    print("\nCONTRACT_SUMMARY category rows:")
    for c in candidates:
        if c.category == "CONTRACT_SUMMARY":
            print(
                f"  label={c.label!r} value={c.value!r} page={c.source_page} "
                f"reasons={c.reason_codes}"
            )

    print("\n" + "=" * 100)
    print("C. FAR/GSAR/DFARS CLASSIFICATION COUNTS")
    print("=" * 100)
    clause_counts = Counter(c.category for c in candidates if c.regulation is not None)
    regulation_counts = Counter(
        (c.category, c.regulation) for c in candidates if c.regulation is not None
    )
    for (category, regulation), count in sorted(regulation_counts.items()):
        print(f"  {regulation} -> {category}: {count}")

    print("\n" + "=" * 100)
    print("D. CATEGORY BREAKDOWN")
    print("=" * 100)
    counts = Counter(c.category for c in candidates)
    for category, count in counts.most_common():
        print(f"  {category}: {count}")

    print("\n" + "=" * 100)
    print("E. CLIN/FUNDING DEDUP CHECK")
    print("=" * 100)
    clin_evidence = {c.evidence for c in candidates if c.category == "CLIN"}
    funding_evidence = {c.evidence for c in candidates if c.category == "FUNDING"}
    overlap = clin_evidence & funding_evidence
    print(f"CLIN candidates: {len(clin_evidence)} | FUNDING candidates: {len(funding_evidence)}")
    print(f"Exact-evidence overlap remaining after dedup: {len(overlap)}")


if __name__ == "__main__":
    main()
