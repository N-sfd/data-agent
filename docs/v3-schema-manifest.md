# V3 Ground-Truth Schema Manifest

Source of truth: `reference/schemas/V3_Extraction.xlsx` (read directly, all sheets, Phase 1 — 2026-09-22).
Contract represented in this ground-truth file: **N40192-23-D-2803** (SB-DBMACC, NAVFAC Marianas), NOT the
regression contract (47QRCA25DSF07). This file is a worked *example* of correct V3 output on a different
contract — it defines the schema/shape, not the regression contract's expected values.

12 sheets total, **all visible** (no hidden sheets). Every data sheet is a native Excel Table
(`ListObject`) with a header row at row 3 (row 1 is a merged title banner, row 2 is blank). Every data
sheet's last column is a `QA Status` (or equivalent) column with an identical one-way data validation
dropdown list:

```
Verified, Needs Review, PASS, REVIEW, Verified — source states NSP/UNDEFINED
```

(applied as an Excel list validation over `<col>4:<col>1000`, i.e. pre-provisioned for up to ~1000 rows
regardless of current row count). No formulas anywhere in the workbook — every cell is a literal value.
No named ranges beyond the per-sheet Excel Tables.

Universal per-record principle (from the README sheet, sheet 12): **only source-supported values are
populated; missing values are not guessed.** Every substantive record carries `Source Page` + `Evidence`
(exact/near-exact quoted source text). CLINs are isolated from ordinary metadata. Funding facts are
separated from task-order-level funding requirements. Clauses are separated from incidental FAR
references.

---

## 1. All Fields

Excel Table: `AllFieldsTbl`, range `A3:H16` (13 data rows in this example).

| # | Column | Type (observed) | Notes |
|---|--------|------|-------|
| A | Category | string | Free-text grouping, e.g. `Contract Identification`, `Dates`, `Financial`, `Performance`, `Classification` — not an enum, but a small closed-ish set in practice |
| B | Normalized Field | string | Human display label, e.g. `Contract Number`, `Award Date`, `NAICS` — never a raw candidate key |
| C | Value | string \| number | Mixed type per row (e.g. `600000000` as number, `"60 months"` as string) |
| D | Source File | string | Filename of the specific source PDF (this is a **multi-document portfolio** — see Source Documents sheet) |
| E | Source Page | integer | 1-based page number within that source file |
| F | Evidence | string | Long-form quoted/near-quoted source excerpt (can span a full paragraph) |
| G | Extraction Method | string | Observed value: `"Deterministic text"` (only value seen in this sample — schema likely also allows an AI/LLM-fallback label, not present in this example) |
| H | QA Status | enum | See universal dropdown list above |

Sample rows (all 13):
`Contract Number`, `Solicitation / RFP`, `Award Date`, `Maximum Aggregate Amount`, `Minimum Guarantee`,
`Base Period`, `Option Periods`, `Maximum Duration`, `NAICS`, `Size Standard`, `Task Order Range`,
`Commencement of Work`, `Place of Performance`.

**This is the accepted/audit dataset — a flat business-field view, not the primary extraction target.**
Every field here also appears, more richly, in Contract Summary and/or Performance Delivery. It is a
cross-cutting index, not a separate source of truth.

---

## 2. CLINs

Excel Table: `CLINsTbl`, range `A3:S7` (4 rows in this example; sheet pre-provisioned to row 1000).

| Col | Column | Notes |
|---|---|---|
| A | CLIN | string, e.g. `"0001"` (zero-padded, kept as text not int) |
| B | Option/Base | string, e.g. `"Base"`, `"Option 1"` |
| C | Description | string |
| D | Pricing Type | string, e.g. `"FFP"` |
| E | Max Quantity | number \| `"UNDEFINED"` — **can be a literal string when source states no value**, not blank |
| F | Unit | string, e.g. `"Each"` |
| G | Unit Price | number |
| H | Max Amount | number |
| I | Status | string, e.g. `"NTE"`, `"NSP"` (Not Separately Priced) |
| J | FOB | string, e.g. `"Destination"` |
| K | Purchase Request | string |
| L | PSC | string (Product/Service Code) |
| M | POP Start | date (ISO string `YYYY-MM-DD`) — **blank when option not yet priced, not fabricated** |
| N | POP End | date |
| O | Ship To | string |
| P | DODAAC | string |
| Q | Source Page | integer |
| R | Evidence | string |
| S | QA Status | enum |

Key ground-truth rule demonstrated: rows 5-7 (options 1-3) have `Max Quantity = "UNDEFINED"`,
`Status = "NSP"`, blank `Unit Price`/`Max Amount`/POP dates — and QA Status is explicitly
`"Verified — source states NSP/UNDEFINED"`, a **distinct QA state from plain `Verified`**, used when a
missing/placeholder value is itself the ground truth (not an extraction failure).

No parent/child CLIN column in this example (flat list, one row per CLIN). **Open question for
implementation** — see gap analysis — the regression contract has a two-level CLIN hierarchy (domain CLIN
containing NAICS sub-CLINs) that this ground-truth example does not exercise.

---

## 3. Funding

Excel Table: `FundingTbl`, range `A3:I6` (3 rows).

| Col | Column | Notes |
|---|---|---|
| A | Funding Level | string, e.g. `"Basic IDIQ"`, `"Task Orders"`, `"Minimum Guarantee"` — **not a CLIN-level ACRN table in this example**, because the source basic-award document has no obligated funds at all |
| B | CLIN | string, links back to CLINs sheet |
| C | Funding Status | string, free text, e.g. `"No funds obligated at basic contract line-item level"` |
| D | Amount | number, blank when not applicable |
| E | Accounting / Appropriation | string, often a narrative note like `"Not stated on SF1442 award"` rather than an actual ACRN string — **this sheet still gets populated even when there is no real accounting/appropriation data, using narrative explaining the absence** |
| F | Purchase Request | string |
| G | Source Page | integer |
| H | Evidence | string |
| I | QA Status | enum |

Critical distinction demonstrated (per README rule): row 4 (`Basic IDIQ`) = actual basic-contract funding
fact (none obligated), row 5 (`Task Orders`) = the *requirement/rule* for how future task orders will be
funded (narrative, not an actual funding record) — **both still get a row**, but they are differentiated
by `Funding Level`, not excluded. This means "funding requirement narrative" is NOT routed to QA/omitted —
it's a legitimate Funding-sheet record, just tagged by level. This nuances the P0 prompt's instruction
("do not classify narrative funding requirements as actual funding") — the ground truth's actual behavior
is: *include it, but with a Funding Level that marks it as a requirement/rule, not an obligated amount*.

---

## 4. Performance Delivery

Excel Table: `PerformanceDeliverTbl`, range `A3:I8` (5 rows).

| Col | Column | Notes |
|---|---|---|
| A | Record Type | string, e.g. `"Period of Performance"`, `"FOB"`, `"Commencement"`, `"Place of Performance"`, `"Task Order Content"` — **open set, not a fixed enum** |
| B | CLIN | string, blank when not CLIN-specific; can be a range like `"0001-0004"` |
| C | Start | date, blank when not applicable |
| D | End / Timing | string — mixes actual dates (`"2028-09-28"`) and relative timing text (`"Within 15 days"`) in the same column |
| E | Location / Destination | string |
| F | Requirement | string, free-text description |
| G | Source Page | integer |
| H | Evidence | string |
| I | QA Status | enum |

---

## 5. Attachments

Excel Table: `AttachmentsTbl`, range `A3:F5` (2 rows).

| Col | Column | Notes |
|---|---|---|
| A | Attachment / Reference | string, e.g. `"Attachment (2)"`, or a section-number list `"Sections 00 21 16, 00 22 16, 00 45 00"` |
| B | Title / Description | string |
| C | Included in Portfolio? | string — **not boolean**; free text like `"Not present among the three extracted portfolio PDFs"` or `"No — expressly excluded..."` |
| D | Source Page | integer |
| E | Evidence | string |
| F | QA Status | enum — note row 4's QA Status is `"Referenced; attachment bytes not available in extracted portfolio set"`, a **custom free-text QA status outside the standard dropdown list**, showing the dropdown is a suggested list, not a hard constraint |

---

## 6. Clauses

Excel Table: `ClausesTbl`, range `A3:I174` (**171 data rows** — by far the largest structured sheet).

| Col | Column | Notes |
|---|---|---|
| A | Regulation | string — observed value `"FAR"` only in this sheet (DFARS clauses go to the separate DFARS sheet, see below) |
| B | Clause Number | string, e.g. `"52.202-1"` |
| C | Clause Title | string |
| D | Alternate / Deviation | string, blank in sampled rows — column exists for `Alternate I` / `(DEVIATION)` annotations |
| E | Effective Date | string, e.g. `"JUN 2020"` (kept as the FAR-style month/year string, not parsed to a date) |
| F | Incorporation Type | string, all sampled rows = `"Incorporated by Reference"` (full-text incorporation is a valid alternate value per FAR 52.103, not observed in this sample) |
| G | Source Page | integer |
| H | Evidence | string — for these rows, evidence is literally just the clause citation line itself (`"52.202-1 Definitions JUN 2020"`), i.e. minimal/compact evidence is acceptable when the source is a bare incorporation-by-reference listing |
| I | QA Status | enum |

**Every sampled row is Regulation=FAR.** The sheet's column A implies it is meant to also carry non-FAR
regulations if a contract incorporates them directly (this ground-truth contract apparently had none) —
confirm against the regression contract's GSAR clauses (see gap analysis; GSAR is not represented anywhere
in this ground-truth workbook, an open schema question).

---

## 7. FAR References

Excel Table: `FARReferencesTbl`, range `A3:G7` (4 rows).

| Col | Column | Notes |
|---|---|---|
| A | FAR Reference | string, e.g. `"FAR 16.505(a)(10)"`, `"FAR 52.215-1"` — **note col A can itself be a clause-shaped citation** (`52.215-1`) when it appears as an incidental reference rather than an incorporated clause |
| B | Reference Type | string, e.g. `"Subpart reference"`, `"Clause reference"` |
| C | Subject / Context | string, short human summary of why it's cited |
| D | Source Page | integer |
| E | Evidence | string, longer narrative excerpt (unlike Clauses sheet's minimal evidence) |
| F | Contract Clause? | string — **not boolean**: observed values `"No"`, `"Reference in task-order procedures"`, `"Yes / modified applicability"` — a nuanced tri/n-state answer, not a strict yes/no |
| G | QA Status | enum |

This confirms the Clause-vs-Reference split is real and intentional: `52.215-1` and `52.222-11`/`52.222-12`
appear here (FAR References), not in the Clauses sheet, because they're cited in narrative/procedural
context rather than formally incorporated by reference in the clauses list.

---

## 8. DFARS

Excel Table: `DFARSTbl`, range `A3:I53` (**50 data rows**).

Identical column structure to Clauses (`Regulation`, `Clause Number`, `Clause Title`, `Alternate /
Deviation`, `Effective Date`, `Incorporation Type`, `Source Page`, `Evidence`, `QA Status`) — Regulation
column = `"DFARS"` throughout. **This confirms DFARS is a fully separate sheet from Clauses, not a
Regulation-column discriminator within one shared sheet**, despite having an identical column layout.
(Contrast with the dormant backend's `document_clause_reference.py`, which uses a single table with a
`clause_family` discriminator — see gap analysis.)

---

## 9. Source Documents

Excel Table: `SourceDocumentsTbl`, range `A3:D6` (3 rows).

| Col | Column | Notes |
|---|---|---|
| A | Source Document | filename string |
| B | Role | string, e.g. `"Primary award / contract"`, `"Government award notice"`, `"Contractor acknowledgement / contacts"` |
| C | Pages | integer, total page count of that source file |
| D | Extraction Status | string, observed value `"Extracted"` only |

Confirms this ground-truth example is a **multi-PDF portfolio** (3 separate source files decomposed from
one submission) — every other sheet's "Source File"/provenance must be able to point to any one of them.
The regression contract (47QRCA25DSF07) is a single 92-page PDF, so this sheet will have exactly 1 row for
it, but the schema must support N.

---

## 10. QA Review

Excel Table: `QAReviewTbl`, range `A3:D10` (5 rows).

| Col | Column | Notes |
|---|---|---|
| A | QA Check | string, e.g. `"Portfolio decomposition"`, `"CLIN completeness"`, `"Funding traceability"`, `"Performance / delivery"`, `"Attachments"` — **one row per logical QA category, not one row per individual flagged field** |
| B | Result | enum-ish string: `"PASS"` or `"REVIEW"` |
| C | Details | string, free-text explanation |
| D | Action | string, free-text remediation guidance, `"None"` when no action needed |

**Important shape finding:** QA Review here is a small (5-row), *category-level* rollup/checklist — not a
per-record issue log. It reads as a human-authored summary of the whole extraction's QA posture, one row
per dataset area, rather than an automatically generated list of every ambiguous/missing/conflicting value
(which is what the P0 prompt's section 16 describes: "Create QA records for: missing expected values,
ambiguous values, conflicting candidates..."). **Resolved** (decision #3, `v3-implementation-plan.md`): the
exported V3 QA Review sheet reproduces this category-level shape exactly; a separate, granular per-record
issue log is tracked internally (feeding this rollup and the UI's review drawer) but is never exported in
place of it.

---

## 11. Contract Summary

Excel Table: `ContractSummaryTbl`, range `A3:R4` (**1 row** — one row per contract, wide format).

| Col | Column |
|---|---|
| A | Contract Number |
| B | Solicitation / RFP |
| C | Contract Vehicle |
| D | Agency / Office |
| E | Contractor |
| F | Award Date |
| G | Ceiling / Max Aggregate |
| H | Minimum Guarantee |
| I | Base Period |
| J | Options |
| K | Max Duration |
| L | Task Order Range |
| M | NAICS |
| N | Size Standard |
| O | Source File |
| P | Source Page |
| Q | Evidence |
| R | QA Status |

Single wide row, not category/label/value pairs like All Fields — this is the canonical **one-row-per-
contract header record**. Sheet is pre-provisioned to row 100 (supports multiple contracts if the workbook
is ever used as a cross-contract rollup, though this example has exactly one).

---

## 12. README

Not a data sheet — a 2-column `Principle` / `Rule` table (5 rows) stating the four ground-truth principles
quoted verbatim in the P0 prompt (ground truth, provenance, CLINs, funding, clauses separation). No Excel
Table object (unlike every other sheet). Per the P0 prompt's own instruction, this does not need to be
generated as extracted business data — it is static documentation of the methodology, safe to reproduce
literally in the Complete-Excel export without any extraction logic behind it.

---

## Cross-sheet observations that affect implementation

1. **QA Status is not a strict enum.** Two sheets (Attachments, CLINs) use free-text QA Status values
   outside the 5-item dropdown list (`"Referenced; attachment bytes not available..."`,
   `"Verified — source states NSP/UNDEFINED"`). The dropdown is UI convenience, not a hard schema
   constraint — validation logic must not reject/coerce these.
2. **Every sheet uses `Source Page` (singular int) + `Evidence` (string), never a bbox or multi-page
   range**, even though the underlying PDFs are multi-page and a record's evidence could theoretically span
   pages. Treat "one anchor page + evidence excerpt" as the provenance contract, not full bbox tracking.
3. **Numbers are stored as native Excel numbers where the source is unambiguous** (amounts, quantities,
   page counts) but **as text where the source itself is symbolic** (`"UNDEFINED"`, `"NSP"`, CLIN codes
   like `"0001"`). Column type is per-value, not a fixed column type — extraction code must preserve the
   literal token when the source states a non-numeric placeholder rather than coercing to 0 or null.
4. **No sheet has zero rows in this example** — even Attachments (2 rows) and FAR References (4 rows) are
   populated, because a real, information-dense federal contract virtually always has at least one item of
   each kind. A genuinely empty V3 dataset for a given contract is a possible but unverified case (not
   demonstrated by this ground-truth file).
