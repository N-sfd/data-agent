# V3 Gap Analysis — Current Backend vs. Ground-Truth V3 Schema

Synthesizes: [`v3-schema-manifest.md`](v3-schema-manifest.md) (ground truth), [`far-master-schema-manifest.md`](far-master-schema-manifest.md),
[`source-to-v3-mapping.md`](source-to-v3-mapping.md) (regression contract), and a direct code survey of
`backend/app/` (file:line citations below; the dormant "Field Explorer" pipeline built ~August 2026).

## Executive summary

There are **two independent backend pipelines today**, sharing only `validate_source_value`/`SourceEvidence`:

1. **Old pipeline** (`jobs.py` → `extraction_job_runner.py` → `extract_by_targets` → `DocumentDetectedTarget`
   / `DocumentMetadataField`) — this is what the live UI (`target-results.tsx`) reads today, and what
   produced the bad screenshot. Generic kv_* candidate discovery, no V3 awareness at all.
2. **Dormant pipeline** (`contract_structured_table_extractor.py`, spec-driven off `STRUCTURED_TABLE_SPECS`
   in `contract_structured_table_schema.py`, writing to 12 normalized tables under `app/models/document_*.py`)
   — built for a different initiative (Field Explorer, per memory), never wired to any frontend, and
   **critically: 7 of its 12 tables have never produced a single row outside unit-test mocks, and the 5
   that have rows only contain synthetic/repeated test-fixture data** (confirmed by direct query of the
   local SQLite DBs — see below). This pipeline is a real, reusable *skeleton*, not a proven, populated
   system. Treat "dormant" as "unbuilt in practice," not "built and just disconnected."

Neither pipeline currently produces 5 of the 12 V3 datasets (Attachments, Contract Summary, QA Review,
Source Documents, All Fields-as-V3-defines-it) at all. Of the 7 datasets that do have *some* structural
analog, only 2 (Clauses/DFARS, CLINs) are close, and both have real, specific gaps against the ground-truth
schema — not just "needs wiring."

## Per-dataset gap table

| V3 Dataset | Closest existing code | Real data ever produced? | Gap vs. ground-truth schema |
|---|---|---|---|
| **CLINs** | `DocumentLineItem` (`document_line_item.py:9-57`: `clin, description, quantity, unit, unit_price, amount, is_maximum, period_label`) + `contract_structured_table_extractor.py` | 23-26 rows across 2 local DBs, but 1 row per document (test fixture) | Missing ~12 of the ground-truth's 19 columns: `Option/Base, Pricing Type, Status, FOB, Purchase Request, PSC, POP Start, POP End, Ship To, DODAAC, QA Status` (has `Source Page`/`Evidence` equiv via `evidence_json`). No parent/child hierarchy for the regression contract's Domain→NAICS-sub-CLIN structure. `clin_block_detector.py` (`clin_block_detector.py:37-76`) *detects* a CLIN table exists but doesn't parse rows into this table — unused for that purpose. |
| **Clauses (FAR)** | `DocumentClauseReference` (`document_clause_reference.py:9-57`, `clause_family: "FAR"\|"DFARS"`) | 45-52 rows, but same 2 clauses repeated across every document (test fixture) | **No discriminator for "actually incorporated" vs. "incidental mention"** — everything with a FAR number lands in one bucket. This is the single biggest structural gap: the ground-truth Clauses sheet (171 rows) and FAR References sheet (4 rows) are *separate datasets*; the current model can't produce that split at all. `clause_citation_scanner.py` (`clause_citation_scanner.py:1-97`) is a deterministic regex FAR/DFARS-number finder with grounding validation that could seed this — **confirmed unused, zero callers outside its own module.** |
| **FAR References** | Same table as Clauses (`DocumentClauseReference`) | Same as above | Same gap as Clauses — no way to route a candidate to one dataset vs. the other; also missing `Reference Type, Subject/Context, Contract Clause?` columns entirely. |
| **DFARS** | Same table, `clause_family = "DFARS"` | Same as above | Structurally the closest fit of all 12 (has `alternate, deviation, variation_effective_date` which map well to ground-truth's `Alternate/Deviation`), but still shares the Clause-vs-Reference gap, and there's no DFARS Master to validate against (per FAR Master manifest — known, accepted limitation, not fixable this phase). |
| **GSAR clauses** (confirmed present in regression contract: `552.252-6`, `552.216-75`, `552.242-99`) | None | Zero | `_build_clause_reference_fields` (`contract_structured_table_extractor.py:129-133`) **hard-codes the valid family set to `{"FAR","DFARS"}`; any other value (including "GSAR") is silently coerced to "FAR"** — this is an active bug waiting to fire the moment this pipeline runs on a GSA contract, not just a missing feature. `clause_citation_scanner.py` has no GSAR regex either. |
| **Funding** | `DocumentFundingLine` (`document_funding_line.py`: `acrn, line_of_accounting, amount`) | Zero rows ever | Only 3 columns vs. ground truth's `Funding Level, CLIN, Funding Status, Amount, Accounting/Appropriation, Purchase Request, Source Page, Evidence, QA Status` (9). No `Funding Level` concept at all — can't represent the ground truth's key distinction (actual obligated funds vs. task-order-funding-rule narrative). |
| **Performance Delivery** | `DocumentPerformancePeriod` (`period_label, start_date, end_date, amount`) **+ separately** `DocumentDeliverySchedule` (`clin, delivery_date, quantity, ship_to_address, dodaac, cage_code`) | Zero rows ever, both tables | Ground truth is **one merged sheet** (`Record Type, CLIN, Start, End/Timing, Location/Destination, Requirement, Source Page, Evidence, QA Status`) covering POP, FOB, Commencement, Place of Performance, Task Order Content as one open `Record Type` set. Current design is two separate, narrower tables with no shared key beyond `document_id` and no `Record Type`/`Requirement`/free-text concept — would need a real merge, not just wiring. |
| **Attachments** | None | N/A | Nothing exists — no model, no extractor, not even a stub. Build from scratch. |
| **Contract Summary** | None (closest: `contract_field_schema.py`'s generic commercial groups `Identification, Parties, Dates, Financial, Legal, Commercial, Compliance, Government`) | N/A | No scalar one-row-per-contract summary model anywhere. The existing generic field schema is commercial-contract-shaped, not government-contract-shaped (no CLIN/ceiling rollup, no NAICS/PSC, no task-order-range concept). Needs new modeling, likely reusing `DocumentMetadataField`-style scalar storage rather than a new table (Contract Summary is structurally just "All Fields, pivoted wide"). |
| **All Fields** (V3 sense: accepted/audit dataset) | `DocumentMetadataField` (old pipeline only) | 3,204-13,305 rows (real production data, unlike the dormant tables) | This is the **one dataset the old pipeline already does reasonably well at the storage layer** — the problem is entirely upstream, in what gets classified as a candidate in the first place (TOC/heading contamination, see mapping doc). Reusing this table's storage shape for V3's All Fields sheet is viable; the *candidate generation feeding it* is what needs the classification/routing rework. |
| **Source Documents** | None dedicated (only base `Document` model) | N/A | No per-document-portfolio rollup (filename, role, page count, extraction status) exists as a dataset. Simple to build (mostly derivable from existing `Document` rows), but doesn't exist today. |
| **QA Review** | None as a dataset — `reviewed_export.py:_needs_review_fields` (`reviewed_export.py:129-145`) computes an on-the-fly filter over `DocumentMetadataField` (rejected/pending status AND validation-failed/low-confidence/empty) | N/A (derived, not stored) | Not a persisted dataset at all today, on either pipeline. All 12 dormant tables carry only a bare `confidence: float`, no issue/flag/reason field. Ground truth's QA Review sheet is also *category-level* (5 rows, one per dataset area), not per-record (see schema manifest's open question) — either way, nothing today produces either shape. Needs new modeling regardless of which shape is chosen. |

## Cross-cutting gaps (not specific to one dataset)

1. **No candidate → V3-category router exists anywhere.** Both pipelines are architecturally
   "one extraction path per dataset type" (old: one flat kv_* stream; dormant: one row per
   `STRUCTURED_TABLE_SPECS` entry, chosen by the AI provider per-spec, not by classifying a shared
   candidate pool). The P0 prompt's required flow (§3-4: structure detection → candidate extraction →
   candidate classification → V3 routing → validation → provenance → QA → canonical dataset) does not
   exist as a single pipeline stage anywhere. This is the largest architectural gap, bigger than any
   single dataset's column list.

2. **Structural contamination (TOC lines, subsection-number splitting, tabular headers) reaching the
   candidate pool is a discovery-time bug in the OLD pipeline**, confirmed concretely in the mapping doc.
   It is *not* automatically fixed by moving to the dormant pipeline — the dormant pipeline is AI-provider-
   driven per spec (not confirmed whether it has the same contamination risk; it has never run on a real
   contract to observe). Structure detection has to happen regardless of which extraction backend
   ultimately produces the rows.

3. **The dormant pipeline's export wiring is mechanical but currently absent.**
   `reviewed_export.py` only imports `DocumentMetadataField` and a generic duck-typed `tables` param —
   zero imports of any of the 15 dormant models. `get_document_structured_tables(db, document_id)`
   (`contract_structured_table_extractor.py:484-500`) already provides the exact `document_id → 12 tables`
   query needed, so this part of §18/§19 of the P0 prompt ("UI and Excel must use the same data") is
   low-risk once the underlying tables are actually populated with real data — the risk is entirely
   upstream (extraction quality/schema completeness), not in the export plumbing.

4. **`document_clause.py`/`contract_clause_extractor.py` is a false friend** — it extracts generic
   commercial clause *types* (Termination, Indemnification, IP, etc. — `contract_clause_schema.py:1-14`),
   completely unrelated to FAR/DFARS/GSAR numbering. Do not reuse or extend this for V3 Clauses; it solves
   a different problem (commercial contract clause taxonomy, not federal-contract regulation citations).

5. **FAR Master enrichment has zero integration today.** No code anywhere references FAR Master data
   (the workbook didn't exist in the repo before this session). The validate/enrich flow described in
   `far-master-schema-manifest.md` needs to be built from scratch: ingest FAR Master into a queryable
   reference table (or load the xlsx directly at request time — a size/performance decision for the
   implementation plan), then wire it as a lookup step after `clause_citation_scanner.py`-style detection.

## Decisions (RESOLVED 2026-09-22 — see `v3-implementation-plan.md`, Phase 0)

The six open questions originally listed here have been decided. Full rules and rationale are in
[`v3-implementation-plan.md`](v3-implementation-plan.md#phase-0--decisions-resolved-approved-2026-09-22);
summary:

1. **CLIN hierarchy** — no V3 schema change. Each CLIN/SLIN/sub-CLIN exports as its own independent row;
   parent/child relationship preserved internally only (`parent_line_item`/`relationship` metadata).
2. **GSAR clause routing** — into the existing Clauses sheet with `Regulation = "GSAR"`. No new sheet.
3. **QA Review shape** — exported sheet matches the ground truth's category-level checklist exactly;
   granular per-record issues tracked internally, feeding that rollup and the UI's review drawer.
4. **Funding "requirement narrative" rows** — included, distinguished via `Funding Level`, never excluded.
5. **Contract Summary's NAICS field** — single administrative NAICS only, blank/Needs Review if
   unsupported; per-domain NAICS list lives in CLINs, never collapsed into this field.
6. **Extraction Method vocabulary** — `native_text, ocr, form_field, table, deterministic, ai_fallback,
   human_review`; AI is fallback-only, never labeled `deterministic` when it materially contributed.

**Overall governing rule**: where any prior instruction conflicts with the inspected `V3_Extraction.xlsx`,
the workbook wins. The backend is never a reason to change V3's schema.
