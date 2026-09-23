# V3 Implementation Plan

Built from [`v3-gap-analysis.md`](v3-gap-analysis.md). This is a **plan for review, not a commitment to
start** — per your instruction, implementation does not begin until you approve the Phase 1 mapping (this
document plus the four others in `docs/`).

## Sequencing principle

The P0 prompt's own §24 order (schema → routing → Contract Summary → CLINs → Clauses/FAR-Refs →
Funding → Performance/Delivery → Attachments/DFARS → QA → UI → Excel/API → regression → report) is sound
and is followed below, but with one structural change driven by the gap analysis: **the candidate
classification/routing layer (§24 step 2) has to be built before *any* individual dataset extractor**,
because right now neither pipeline has one — building CLINs first and routing second (as a literal reading
of §24 might suggest) would mean building CLIN extraction against the old pipeline's contaminated candidate
stream, then throwing that work away once routing exists. Routing is a prerequisite, not step 2 of 12.

Also, per the gap analysis: the dormant pipeline's tables are schema skeletons with **no real production
data behind them** (7 of 12 families have zero rows ever; the other 5 are test-fixture-only). "Wire up the
dormant pipeline" is not a shortcut — most of the actual work is building real, working extraction against
each dataset's ground-truth schema, using the dormant models as a starting *shape* where they're close
(CLINs, DFARS) and building new ones where they're not (Funding, Performance/Delivery needs a merge,
Attachments, Contract Summary, QA Review, Source Documents).

## Phase 0 — Decisions (RESOLVED, approved 2026-09-22)

**Overall rule (governs all six, and any future conflict between the P0 prompt's generic wording and the
inspected workbook): `V3_Extraction.xlsx` wins.** Source contract determines facts/presence. V3 determines
output structure. FAR Master validates/enriches FAR information. The canonical backend may retain richer
provenance/relationships internally, but never adds a column to the V3 workbook schema just to make the
backend's life easier.

| # | Decision | Rule |
|---|---|---|
| 1 | CLIN hierarchy | **No new column in the V3 CLINs sheet.** Each CLIN/SLIN/sub-CLIN is exported as its own row using the existing 19 V3 columns. But the relationship is **not discarded** — the canonical internal model retains `parent_line_item`/`relationship` (e.g. SLIN-of) when the source establishes it, as provenance/internal metadata that simply has no V3 column to land in. See "Canonical internal CLIN model" below. |
| 2 | GSAR | Route into the existing **Clauses** dataset with `Regulation = "GSAR"`. No new sheet — the `Regulation` column already exists precisely to carry this distinction. DFARS keeps its own dedicated sheet because V3 already defines one explicitly; GSAR gets no equivalent because V3 doesn't define one. |
| 3 | QA Review | **Reproduce the exact ground-truth shape** — category-level checklist (one row per dataset area: Contract Summary, CLINs, Funding, Performance/Delivery, Attachments, Clauses, FAR References, DFARS — PASS/REVIEW + Details + Action), not a granular per-record issue log. Granular issues are still tracked internally (linked to affected records, for UI/source review), but the **exported V3 QA Review sheet must match the workbook exactly.** |
| 4 | Funding narrative rows | **Follow the ground truth: include them.** My earlier instruction to exclude narrative funding-requirement rows is superseded. Use the exact `Funding Level` vocabulary the ground-truth sheet demonstrates (`"Basic IDIQ"`, `"Task Orders"`, `"Minimum Guarantee"`, etc., extended as new legitimate levels are discovered) so actual obligated funding stays distinguishable from task-order/future funding requirement narrative — via the `Funding Level` column, never via silent omission. |
| 5 | Contract Summary NAICS | **Single, contract-level administrative NAICS only**, when source-supported (e.g. this contract's `541990` "OASIS+ Solicitation NAICS Code"). Never collapse the full per-domain NAICS list into this scalar field. If no single administrative NAICS is source-supported, the value is **blank / Needs Review** — never inferred/guessed from the domain list. Detailed per-domain/per-CLIN NAICS codes live in CLINs (or wherever V3 places them), not here. |
| 6 | Extraction Method | Record the method **actually responsible for the accepted value** — vocabulary at minimum: `native_text, ocr, form_field, table, deterministic, ai_fallback, human_review`. AI remains a **fallback**, never the default strategy, and a value AI materially supplied/resolved must never be labeled `deterministic`. Prefer vocabulary already established by V3/current code (the ground truth's own observed value, `"Deterministic text"`, maps to `deterministic`) over inventing unnecessary new variants. |

### Canonical internal CLIN model (decision #1, detail)

Not a V3 schema change — an internal representation only, so the parent/child relationship the source
establishes isn't lost even though it has nowhere to go in the exported workbook:

```
Canonical internal record                    V3 CLINs sheet (unchanged, 19 cols)
--------------------------                    -----------------------------------
clin = "0001"                                  0001    ...
slin = null
parent_line_item = null
relationship = null
                                    ---->
clin = "0001AA"                                0001AA  ...
slin = "0001AA"
parent_line_item = "0001"
relationship = "SLIN"
```

Applies equally to the regression contract's Domain→NAICS-sub-CLIN shape (`10300` domain CLIN,
`10301`-`10316` NAICS sub-CLINs each with `parent_line_item = "10300"`, `relationship = "DOMAIN_NAICS"`).
Every sub-CLIN still gets its own independent, fully-populated V3 row per the ground-truth schema —
the hierarchy lives only in internal metadata alongside the existing evidence/provenance data, not as a
new exported column.

## Phase 1 — Structure detection & candidate classification/routing (foundation)

This is the layer neither pipeline has. Scope:
- A page/layout structure pass that tags text as one of: form-field-label-region (like the regression
  contract's SF33 page 2, which needs position-sorted extraction, not plain text order — confirmed
  necessary in the mapping doc), running narrative, table row, Table-of-Contents line, section heading,
  tabular column header. This is what's missing that lets TOC lines and subsection-number artifacts (the
  confirmed root cause of the screenshot's bad fields) get excluded *before* they ever become kv_*
  candidates, rather than being filtered after the fact (the current, evidently leaky, approach per commit
  `5492415`'s incomplete TOC filter).
- A classifier that takes a structurally-clean candidate and assigns it one of the 14 categories from the
  P0 prompt (§4): CONTRACT_SUMMARY, CLIN, FUNDING, PERFORMANCE_DELIVERY, ATTACHMENT, CLAUSE, FAR_REFERENCE,
  DFARS, GENERAL_ACCEPTED_FIELD, SOURCE_DOCUMENT_METADATA, QA_REVIEW, STRUCTURAL_HEADING, NARRATIVE, NOISE.
- Reuse where it fits: `clause_citation_scanner.py`'s deterministic FAR/DFARS regex + grounding check is
  already exactly the right shape for CLAUSE/FAR_REFERENCE/DFARS candidate generation — it just needs (a)
  a GSAR pattern added, (b) a "which listing context is this citation in" signal (Section I incorporation
  list vs. narrative) to split CLAUSE from FAR_REFERENCE, and (c) to actually be called by something.
  `clin_block_detector.py` similarly already detects CLIN table regions; extend it to parse rows instead
  of just flagging block existence.

Acceptance: run against the regression contract, confirm none of the 7 confirmed bad-screenshot values
(Solicitation Number, NAICS, B.8, C.1, F.4, F.5, Adm 4800) survive classification as a business field —
they should land in STRUCTURAL_HEADING or NARRATIVE instead.

## Phase 2 — Contract Summary

Scalar, one-row-per-contract. Reuses `DocumentMetadataField`-style scalar storage (the old pipeline's
storage layer is fine; only candidate generation was the problem). New: a fixed Contract Summary field set
matching the ground-truth schema's 18 columns, sourced from CONTRACT_SUMMARY-classified candidates. Per
decision #5: `NAICS` gets the single contract-level administrative NAICS only when source-supported, blank
+ Needs Review otherwise — never an inferred/aggregated value from the per-domain NAICS list.

## Phase 3 — CLINs

Extend `DocumentLineItem` per the gap analysis's column list (`Option/Base, Pricing Type, Status, FOB,
Purchase Request, PSC, POP Start, POP End, Ship To, DODAAC, QA Status`) — these all map to real V3 columns,
so this is a legitimate model extension, not a V3 schema change. Additionally add the **internal-only**
`slin, parent_line_item, relationship` fields per decision #1 — never exported to the V3 CLINs sheet, used
only to keep the source's hierarchy from being silently lost. Extend `clin_block_detector.py` to actually
parse rows (currently detection-only). Preserve multiline descriptions (P0 §6). Regression acceptance:
every CLIN/sub-CLIN (including the regression contract's two-level Domain/NAICS structure) exports as its
own independent V3 row with all 19 ground-truth columns populated, `$0.00`-obligated-amount rows appearing
*as CLIN-table columns* rather than orphan scalars (resolves the screenshot's "Amount → $0.00" complaint —
the value was already correct, only the routing was wrong), and the parent/child relationship recoverable
from internal metadata even though it has no V3 column.

## Phase 4 — Clauses vs. FAR References vs. DFARS vs. GSAR

The single biggest gap. Build the CLAUSE/FAR_REFERENCE discriminator (Phase 1 classifier output) into
`DocumentClauseReference`, or split into two queries/views over one table — implementation detail, not a
schema question, as long as the V3 export sees them as two separate sheets. Per decision #2: fix the
hard-coded `{"FAR","DFARS"}` family set (`contract_structured_table_extractor.py:129-133`) to also accept
`"GSAR"`, routed into the **same Clauses sheet/table** as FAR (not a new sheet) — `Regulation` column
already carries the distinction. DFARS keeps its existing separate table/sheet unchanged. Wire FAR Master
validation/enrichment (per `far-master-schema-manifest.md`'s lookup flow) as a post-extraction step — ingest
the FAR Master workbook into a queryable form once (likely a lookup table keyed on `FAR Number`, loaded at
startup or lazily cached; xlsx-per-request would be too slow given 757 rows × large text columns; note FAR
Master has no GSAR coverage, so GSAR clauses get no enrichment step, same accepted limitation as DFARS).
Regression acceptance: the ~13 Section-I incorporated clauses (including 2 GSAR ones, `Regulation="GSAR"`)
land in Clauses; the ~17+ incidental citations (`FAR 52.219-14`, `FAR 52.204-15`, etc.) land in FAR
References; zero cross-contamination between the two sheets.

## Phase 5 — Funding

Extend `DocumentFundingLine` with the ground truth's missing columns (`Funding Level, CLIN, Funding
Status, Accounting/Appropriation, Purchase Request`). Per decision #4: task-order/future-funding
requirement narrative is **included**, tagged via `Funding Level` (extending the ground truth's observed
vocabulary — `"Basic IDIQ"`, `"Task Orders"`, `"Minimum Guarantee"` — as new legitimate levels are found),
never silently dropped. Regression acceptance: correctly produces a small Funding sheet with rows for both
"no funds obligated at basic-contract level" (actual fact) and "task orders fund individually upon
issuance" (requirement narrative, distinguishable by `Funding Level`) — this IDIQ has no ACRN data at all
(confirmed in the mapping doc), so a small, narrative-heavy Funding sheet is the *correct* output, not a
gap to fill.

## Phase 6 — Performance Delivery

Merge `DocumentPerformancePeriod` + `DocumentDeliverySchedule` into the ground truth's single
`Record Type`-discriminated shape, or keep two tables internally and merge only at export time (lower-risk,
avoids a destructive migration) — recommend the latter unless you prefer a real merge. Either way, add the
missing `Requirement` free-text column and keep `Record Type` open (not a fixed enum — confirmed necessary
by both the ground truth and the regression contract showing Record Types beyond the one example).

## Phase 7 — Attachments & (DFARS already covered in Phase 4)

Attachments has no existing code — build the model, classifier hook (ATTACHMENT category from Phase 1),
and extractor from scratch. Regression acceptance: correctly split the regression contract's Section J into
J.1 (remains with contract, 8 items) vs. J.2 (RFP-only, excluded, 11 items including 2 Reserved) using the
"Included in Portfolio?"-style free-text distinction from the ground truth.

## Phase 8 — QA Review

Per decision #3: the **exported** V3 QA Review sheet is a category-level checklist matching the ground
truth exactly — one row per dataset area (Contract Summary, CLINs, Funding, Performance/Delivery,
Attachments, Clauses, FAR References, DFARS), each with `PASS`/`REVIEW` + `Details` + `Action`. This is a
rollup computed post-extraction from each phase's own results — closer to `reviewed_export.py`'s existing
`_needs_review_fields` filter pattern than to a new table. Separately (internal only, not exported to this
sheet): persist a granular issue log — per-record ambiguous/missing/conflicting/low-confidence/unmatched-
FAR-clause/date-mismatch/title-mismatch entries, linked to the affected record — for the UI's source-review
drawer to surface, and for the category-level rollup above to be computed *from* (a category is `REVIEW` if
its granular issue log is non-empty, `PASS` otherwise). Also build Source Documents in this phase (simple,
derivable from existing `Document` rows plus a per-file role classification).

## Phase 9 — UI consumes canonical V3 datasets

Replace `target-results.tsx`'s current tabs (All Fields / Key Contract Fields / Sections / Line Items /
Tables / Needs Review) with the V3-shaped tabs (Contract Summary, CLINs, Funding, Performance Delivery,
Attachments, Clauses, FAR References, DFARS, All Fields, QA Review, Source Documents — per P0 §17). Each
tab reads directly from its canonical dataset's API response, not from a shared "All Fields" superset that
gets re-classified client-side.

## Phase 10 — XLSX/CSV/API consume the same datasets

Wire `reviewed_export.py` to the same canonical dataset queries the UI uses (per gap analysis §3, the
plumbing — `get_document_structured_tables`-equivalent queries — is mechanical once the datasets
themselves are real; this phase is verification that UI and Excel numbers match exactly, not new
extraction logic). Sheet order/names/columns per the ground-truth manifest exactly, README sheet
reproduced statically (not extracted, per the P0 prompt's own instruction).

## Phase 11 — Regression run & before/after report

Re-run the full pipeline against `Contract_47QRCA25DSF07 (2).pdf`. Produce the before/after table the P0
prompt asks for (§21) — the mapping doc already has the "before" (screenshot) and "actual source" columns
filled in for all 7 confirmed examples; this phase adds the "after" (new classification/value/V3
destination/validation status) once the pipeline actually runs. Report the §22 acceptance-criteria counts
(records populated/missing/needs-review per dataset, kv_* visible count [must be 0], provenance-missing
count [must be 0]).

## What this plan deliberately does not do

Per your explicit instruction ("do not spend more time polishing the generic All Fields UI before these
canonical datasets exist"), this plan does not include any further work on the old kv_*/`target-results.tsx`
pipeline beyond Phase 1's structural-contamination fix (which benefits the eventual All Fields V3 sheet
too, since that sheet reuses the same storage layer) and Phase 9's tab replacement. No new features, no
NormalizedDocument refactor, no contacts work — all still deferred per your standing instruction from
earlier in this engagement, now effectively superseded/absorbed by this V3 work rather than separately
blocking it.

## Extraction Method vocabulary (decision #6)

Applies wherever any V3 dataset records how an accepted value was obtained (All Fields' `Extraction
Method` column being the most visible, but the same field belongs internally on every dataset's records
for provenance, not just All Fields):

| Value | Meaning |
|---|---|
| `native_text` | Extracted from the PDF's native text layer, position-aware where needed (e.g. SF33 form fields, per the mapping doc's page-2 finding) |
| `ocr` | Extracted from OCR output (scanned/image-based page) |
| `form_field` | Extracted from an actual PDF form field (AcroForm), not text-layer inference |
| `table` | Extracted from a detected table structure (e.g. CLIN schedule) |
| `deterministic` | Regex/rule-based extraction with no ML/AI involvement — maps to the ground truth's observed `"Deterministic text"` |
| `ai_fallback` | AI/LLM materially supplied or resolved the value — **only used when the above methods didn't already produce a source-grounded value**, never the default path |
| `human_review` | Value corrected/confirmed by a human reviewer post-extraction |

A value must never be labeled `deterministic` if AI materially contributed to it, and `ai_fallback` is
reached only after deterministic/structural methods have had a chance to resolve the field.

---

## Status

**Phase 0 decisions: approved 2026-09-22** (table above). **Phase 1 documentation: complete**, all five
documents in `docs/` (`v3-schema-manifest.md`, `far-master-schema-manifest.md`, `source-to-v3-mapping.md`,
`v3-gap-analysis.md`, this file), committed as a documentation-only checkpoint per your instruction — no
production code changed. **Phase 2 implementation has not started** and will not start until you confirm
the pre-Phase-2 checkpoint (files committed, canonical model summary, proposed Phase 2 scope, DB migration
needs) presented separately in chat.
