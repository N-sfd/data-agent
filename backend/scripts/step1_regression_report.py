"""Step 1 regression report: runs structure detection + candidate routing
against the actual regression contract (reference/regression/
Contract_47QRCA25DSF07 (2).pdf) end to end, in memory, with zero database
writes - proves Step 1 against the real document the bad screenshot came
from, not a synthetic stand-in.

Usage: python backend/scripts/step1_regression_report.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import fitz  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.services.candidate_router import (  # noqa: E402
    route_clause_citations,
    route_clin_rows,
    route_page_regions,
)
from app.services.clause_citation_scanner import scan_pages_for_clause_citations  # noqa: E402
from app.services.clin_block_detector import parse_clin_rows  # noqa: E402
from app.services.generic_table_extractor import extract_page_tables  # noqa: E402
from app.services.page_text_extractor import extract_page  # noqa: E402
from app.services.structure_classifier import (  # noqa: E402
    build_document_context,
    classify_page_regions,
)

PDF_PATH = BACKEND_ROOT.parent / "reference" / "regression" / "Contract_47QRCA25DSF07 (2).pdf"

KNOWN_BAD_EXAMPLES = [
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

POSITIVE_FIELD_TARGETS = [
    "CONTRACT NUMBER",
    "SOLICITATION NUMBER",
    "DATE ISSUED",
    "REQUISITION",
]


def main() -> None:
    started = time.perf_counter()
    settings = Settings()
    doc = fitz.open(str(PDF_PATH))
    page_count = doc.page_count
    print(f"Loaded {PDF_PATH.name}: {page_count} pages")

    all_blocks_by_page: dict[int, list] = {}
    all_text_by_page: dict[int, str] = {}
    all_tables_by_page: dict[int, list] = {}
    page_heights: dict[int, float] = {}
    context_input: list[tuple[int, list, float]] = []

    for page_index in range(page_count):
        extraction = extract_page(
            document=doc,
            page_index=page_index,
            settings=settings,
            run_ocr=False,
        )
        page_number = extraction.page_number
        all_blocks_by_page[page_number] = extraction.blocks
        all_text_by_page[page_number] = extraction.final_text
        page_heights[page_number] = extraction.page_height
        context_input.append((page_number, extraction.blocks, extraction.page_height))

        try:
            tables = extract_page_tables(str(PDF_PATH), page_number)
        except Exception:
            tables = []
        all_tables_by_page[page_number] = tables

    extraction_elapsed = time.perf_counter() - started
    print(f"Page extraction (text/blocks/tables, no OCR): {extraction_elapsed:.1f}s")

    classify_started = time.perf_counter()
    doc_context = build_document_context(pages=context_input)

    regions_by_page = {}
    for page_number in range(1, page_count + 1):
        regions_by_page[page_number] = classify_page_regions(
            page_number=page_number,
            blocks=all_blocks_by_page[page_number],
            tables=all_tables_by_page[page_number],
            page_height=page_heights[page_number],
            doc_context=doc_context,
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
        candidates.extend(route_page_regions(regions_by_page[page_number]))
    candidates.extend(route_clause_citations(citations))
    candidates.extend(route_clin_rows(clin_rows))

    total_elapsed = time.perf_counter() - started
    print(
        f"Classification+routing: {classify_elapsed:.1f}s | "
        f"total (incl. text/table extraction): {total_elapsed:.1f}s "
        f"for {page_count} pages -> {total_elapsed / page_count * 1000:.0f}ms/page"
    )
    print(f"Total structural regions: {sum(len(r) for r in regions_by_page.values())}")
    print(f"Total classified candidates: {len(candidates)}")
    print(f"Clause citations found: {len(citations)} | CLIN rows parsed: {len(clin_rows)}")

    print("\n" + "=" * 100)
    print("KNOWN BAD EXAMPLES - before/after")
    print("=" * 100)
    for old_field, old_value in KNOWN_BAD_EXAMPLES:
        print(f"\nOLD FIELD: {old_field!r}  OLD VALUE: {old_value!r}")
        matches = [
            c
            for c in candidates
            if old_field.lower() in (c.evidence or "").lower()
            or (c.label and old_field.lower() in c.label.lower())
        ]
        if not matches:
            print("  -> no candidate found containing this text (likely correctly excluded pre-candidate)")
            continue
        for c in matches[:3]:
            print(
                f"  NEW CATEGORY: {c.category}  CONFIDENCE: {c.confidence:.2f}  "
                f"STRUCTURE: {c.region_type}  PAGE: {c.source_page}"
            )
            print(f"  REASON: {', '.join(c.reason_codes)}")
            print(f"  EVIDENCE: {c.evidence[:160]!r}")

    print("\n" + "=" * 100)
    print("POSITIVE FIELD PRESERVATION")
    print("=" * 100)
    contract_summary_candidates = [c for c in candidates if c.category == "CONTRACT_SUMMARY"]
    print(f"Total CONTRACT_SUMMARY candidates: {len(contract_summary_candidates)}")
    for c in contract_summary_candidates:
        print(f"  {c.label!r} = {c.value!r}  (page {c.source_page}, confidence {c.confidence:.2f})")

    print("\n" + "=" * 100)
    print("CLAUSE POSITIVE TEST (Section I incorporated-clauses listing)")
    print("=" * 100)
    clause_candidates = [c for c in candidates if c.category in ("CLAUSE", "DFARS")]
    print(f"Total CLAUSE/DFARS candidates: {len(clause_candidates)}")
    for c in clause_candidates[:20]:
        print(
            f"  {c.regulation} {c.clause_number}  {c.value!r}  "
            f"category={c.category}  page={c.source_page}  confidence={c.confidence:.2f}"
        )

    print("\n" + "=" * 100)
    print("FAR_REFERENCE sample (incidental citations)")
    print("=" * 100)
    far_ref_candidates = [c for c in candidates if c.category == "FAR_REFERENCE"]
    print(f"Total FAR_REFERENCE candidates: {len(far_ref_candidates)}")
    for c in far_ref_candidates[:10]:
        print(f"  {c.clause_number}  page={c.source_page}  evidence={c.evidence[:100]!r}")

    print("\n" + "=" * 100)
    print("CATEGORY BREAKDOWN")
    print("=" * 100)
    from collections import Counter

    counts = Counter(c.category for c in candidates)
    for category, count in counts.most_common():
        print(f"  {category}: {count}")

    print("\n" + "=" * 100)
    print("STRUCTURAL_HEADING sample (must include the confirmed TOC/heading contamination)")
    print("=" * 100)
    heading_candidates = [c for c in candidates if c.category == "STRUCTURAL_HEADING"]
    naics_codes_hits = [c for c in heading_candidates if "NAICS Codes" in c.evidence]
    toc_fragment_hits = [
        c for c in heading_candidates if c.evidence.strip().startswith(("B.8.1", "C.1.1", "F.4.1"))
    ]
    print(f"Total STRUCTURAL_HEADING: {len(heading_candidates)}")
    print(f"'...NAICS Codes' TOC lines correctly excluded: {len(naics_codes_hits)}")
    for c in naics_codes_hits[:3]:
        print(f"  {c.evidence!r} (page {c.source_page})")
    print(f"B.8.1/C.1.1/F.4.1 fragments correctly excluded: {len(toc_fragment_hits)}")
    for c in toc_fragment_hits[:3]:
        print(f"  {c.evidence!r} (page {c.source_page})")


if __name__ == "__main__":
    main()
