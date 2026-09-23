# Source → V3 Mapping (Regression Contract)

Source: `reference/regression/Contract_47QRCA25DSF07 (2).pdf`, 92 pages, read directly via PyMuPDF
(`fitz`), full text extracted with page markers to a scratch file and inspected with targeted greps plus
a position-sorted block extraction of page 2 (to resolve SF33 form field label/value pairs that plain
text order scrambles). This is the exact document that produced the bad screenshot referenced in the P0
prompt — no substitute/similar contract used.

Contract identity: **GSA OASIS+ MAC (Multiple Award Contract) Program, Small Business IDIQ**, Contract No.
`47QRCA25DSF07`, Contractor CHUGACH BATTELLE APPLIED SOLUTIONS JV LLC. This is structurally different from
the V3 ground-truth example contract (a single-award NAVFAC construction IDIQ) — it's a **multi-domain,
NAICS-based master IDIQ** with hierarchical CLINs and no task-order-level funding data present at all
(base-award document only). The mapping below notes every place this contract's shape stresses the V3
schema differently than the ground-truth example did.

## Contract Summary

Resolved via position-sorted extraction of page 2 (SF33 header block), not plain text order — plain
`get_text()` scrambles SF33 form fields badly (see "Root cause" section below).

| V3 field | Value | Source page | Evidence |
|---|---|---|---|
| Contract Number | `47QRCA25DSF07` | 2 | Item 2 block, position (x=20,y=53) |
| Solicitation / RFP | `47QRCA23R0001` | 2 | Item 3 block, position (x=202,y=53) |
| Contract Vehicle | `OASIS+ SB` (GSA OASIS+ Small Business MAC) | 1, 17 | "GSA One Acquisition Solution for Integrated Services Plus (OASIS+) Contract"; "GSA OASIS+ MAC Program Small Business IDIQ" (page footer, repeated every page) |
| Agency / Office | GSA/FAS, PSHC/SERVICES IDIQ | 2 | Item 7 block |
| Contractor | CHUGACH BATTELLE APPLIED SOLUTIONS JV LLC | 1 | letterhead |
| Award Date | `04/15/2025` | 1 | "Award Date: 04/15/2025" |
| Date Issued | `02/03/2025` | 2 | Item 5 block |
| Requisition/PR Number | `PR-24-0000408` | 2 | Item 6 block |
| UEID | `LLKXZRFEQMR3` | 1 | letterhead |
| NAICS | **no single value** — this contract assigns NAICS per-Domain (8 domains × multiple NAICS each) plus one administrative "OASIS+ Solicitation NAICS Code" `541990` | 17 | "OASIS+ Solicitation NAICS Code: ... assigned a single NAICS Code (541990)..." |
| Period of Performance | 5-year base + one 5-year option (max 10 years) | 45 (text line ~2020) | "OASIS+ has a five year base period of performance with one option period of five years..." |

**Resolved (decision #5, see `v3-implementation-plan.md`):** the single administrative NAICS (`541990`)
goes in Contract Summary; the full per-domain NAICS list routes to the CLINs sheet (each CLIN already
carries a NAICS-shaped code, e.g. `RD-541330-SB`). Never collapse multiple domain NAICS codes into the
Contract Summary field; if no single administrative NAICS were source-supported, that field would be
blank/Needs Review rather than inferred.

## CLINs

Grep-confirmed at page 3 (`OPTIONAL FORM 336` continuation sheet, Section B pricing schedule). Structure
is **two-level**: a Domain-level CLIN (5-digit code like `10300`) containing multiple NAICS-level sub-CLINs
(like `10301`-`10316`), each with its own description, price (`0.00` — IDIQ ceiling placeholder, no task
order priced yet), and an `Obligated Amount: $0.00` line.

Example (page 3):
```
00001   Funding Line                                    2,500.00
10300   RD0003 - Research and Development - This Domain      0.00
        includes any requirements in support of Research
        and Development (R&D) activities...
        Obligated Amount: $0.00
10301   RD-541330-SB                                         0.00
        541330 Engineering Services
        Obligated Amount: $0.00
10302   RD-541330E1-SB                                        0.00
        541330 (Exception 1) Military and Aerospace
        Equipment and Military Weapons
        Obligated Amount: $0.00
```

This continues for all 8 Domains (Management & Advisory, Technical & Engineering, R&D, Intelligence
Services, Enterprise Solutions [Reserved], Environmental, Facilities, Logistics — per the TOC at
`C.2.1`-`C.2.8`), each with its own NAICS sub-CLIN list.

**`00001 Funding Line = 2,500.00` is a real, distinct line** — not a domain/NAICS CLIN, likely an
administrative registration/access fee (OASIS+ contracts commonly have a Contract Access Fee — confirmed
elsewhere in the doc at "Task Order, Transactional Data, and Contract Access Fee Reporting", Attachment
J-2). This should NOT be misfiled as a Domain CLIN; it's its own CLIN type.

**Root-cause note for the screenshot's `Amount -> $0.00`**: this is **not wrong data**. `$0.00` is the
correct, source-supported obligated amount for every Domain/NAICS CLIN on this base IDIQ award (no task
order has been issued yet — funds are obligated only at task-order level, same pattern as the V3
ground-truth Funding sheet's `"Basic IDIQ" -> "No funds obligated at basic contract line-item level"`
row). The actual defect is that the current pipeline surfaces this `$0.00` as a lone scalar `"Amount"` row
in All Fields with no CLIN code, no description, no NAICS context attached — instead of as one column
inside a properly structured CLIN row where `$0.00` makes sense in context. Fix target: route to CLINs
sheet, not "make the number different."

**Resolved (decision #1, see `v3-implementation-plan.md`):** no new V3 column. Every Domain CLIN and every
NAICS sub-CLIN exports as its own independent, fully-populated row using the existing 19 CLINs columns.
The parent/child relationship (`10300` domain CLIN → `10301`-`10316` NAICS sub-CLINs) is preserved only in
the canonical internal model's `parent_line_item`/`relationship` metadata, not in the exported workbook.

## Funding

This is a **basic IDIQ award document only** — same situation as the ground-truth example. No ACRN/
accounting-classification data exists anywhere in the 92 pages (grepped, none found) beyond the per-CLIN
`Obligated Amount: $0.00` lines already covered under CLINs, and the `$2,500.00` Funding Line. Expected
Funding-sheet output for this contract: a small number of rows describing "no funds obligated at the
basic-contract level, funding occurs at task-order issuance" (narrative-rule row, same `Funding Level`
distinction as the ground-truth example), not a populated ACRN table — **this is correct/expected, not a
gap**.

## Performance Delivery

Page 45 area (Section F, `F.3 PERIOD OF PERFORMANCE`): "OASIS+ has a five year base period of performance
with one option period of five years that may extend the cumulative term of the contract to ten years in
accordance with FAR 52.217-9, Option to Extend the Term of the Contract, if exercised." Maps cleanly to a
`Record Type = "Period of Performance"` row, no CLIN association (contract-wide, not CLIN-specific — unlike
the ground-truth example where POP was tied to CLIN 0001).

`F.4 PERFORMANCE STANDARDS` / `F.4.1 Deliverable and Reporting Requirements` (page 32 per TOC) and `F.5
CONTRACTOR PERFORMANCE` (page 39, includes CPARS reporting requirements) are additional Performance
Delivery-shaped content this contract has that the ground-truth example didn't — confirms Record Type
needs to stay an open/free-text set (as the manifest already notes), not a fixed enum limited to the 5
values seen in the one ground-truth example.

## Attachments

Page 92 (Section J), **cleanly enumerated, no ambiguity**:

**J.1 Master Contract Attachments (remain with the executed contract):**
J-1 OASIS+ Labor Categories and BLS Standard Occupational Classifications; J-2 Task Order, Transactional
Data, and Contract Access Fee Reporting; J-3 Cybersecurity & Supply Chain Risk Management (C-SCRM)
Deliverables; J-4 DoD Required Provisions and Clauses for Task Orders; J-5 OASIS+ Task Order Clause and
Provision Matrix; J-6 Awarded Sole Source T&M/L-H Ceiling Rates; J-7 Professional Employee Compensation
Plan (PECP); J-8 Meaningful Relationship Commitment Letter(s).

**J.2 RFP Solicitation Attachments (explicitly do NOT remain with the executed contract):**
J.P-1 through J.P-9 (Domain Qualifications Matrix, FPDS Sample, Project Verification Form, Auto-Relevant
NAICS/PSCs, Functional Areas, Past Performance Rating Form, JV Work Template, Direct Labor Rate Ranges,
Cost/Price Template), plus J.P-10/J.P-11 `Reserved`.

This is a clean, unambiguous "Included in Portfolio?" distinction — directly analogous to the
ground-truth Attachments sheet's own such column, and should map straightforwardly (J.1 items =
`"Yes"`-shaped answer since they're part of the master contract; J.2 items = `"No — RFP-only, excluded
from executed contract"`-shaped answer, mirroring the ground truth's own free-text pattern for this
column).

## Clauses (actual incorporated clauses) vs FAR References (incidental citations) vs DFARS vs GSAR

This is the contract's richest, most important distinction, and the regression PDF has a textbook-clean
example of it.

**Actual incorporated clauses — Section I (`I.2 MASTER CONTRACT CLAUSES`, pages 74-90), a short, explicit,
numbered list — ~13 items total:**

| Clause | Title | Date | Notes |
|---|---|---|---|
| FAR 52.252-2 | Clauses Incorporated by Reference | Feb 1998 | |
| GSAR 552.252-6 | Authorized Deviations in Clauses | NOV 2021 | `(Deviation FAR 52.252-6)` |
| FAR 52.204-21 | Basic Safeguarding of Covered Contractor Information Systems | — | |
| FAR 52.204-30 | Federal Acquisition Supply Chain Security Act Orders-Prohibition | — | |
| FAR 52.216-18 | Ordering | APR 2023 | `(DEVIATION)` |
| FAR 52.216-19 | Order Limitations | OCT 1995 | |
| FAR 52.216-22 | Indefinite Quantity | APR 2023 | `(DEVIATION)` |
| FAR 52.217-8 | Option To Extend Services | NOV 1999 | |
| FAR 52.217-9 | Option To Extend the Term of the Contract | MAR 2000 | |
| FAR 52.222-35 | Equal Opportunity for Veterans | JUN 2020 | |
| FAR 52.222-36 | Equal Opportunity for Workers with Disabilities | JUN 2020 | |
| GSAR 552.216-75 | Transactional Data Reporting | MAY 2023 | |
| GSAR 552.242-99 | Cancellation (Non-Schedules) | Apr 2023 | |

**This introduces a THIRD regulation family — GSAR (552.xxx-x, General Services Administration
Acquisition Regulation) — not present anywhere in the V3 ground-truth workbook**, which only ever shows
`Regulation = "FAR"` (Clauses sheet) or `"DFARS"` (DFARS sheet). GSAR clauses are structurally identical
(number/title/date/incorporation type). **Resolved (decision #2, see `v3-implementation-plan.md`)**: route
GSAR into the Clauses sheet with `Regulation = "GSAR"` — no new sheet, since the ground truth defines no
GSAR sheet and the existing `Regulation` column already carries this distinction. DFARS keeps its
dedicated sheet unchanged, since V3 explicitly defines one for it.

**Incidental FAR/DFARS citations scattered through narrative** (NOT part of the Section I incorporation
list — these are routine in-text references like "in accordance with FAR 52.219-14" or "FAR 52.222-37"),
found throughout Sections F/G: `FAR 52.216-29/30/31`, `FAR 52.232-7`, `FAR 52.246-4`, `FAR 52.242-15`,
`FAR 52.247-34`, `FAR 52.204-25`, `FAR 52.219-28`, `FAR 52.204-15`, `FAR 52.219-14` (appears at least 3
times in different sections), `FAR 52.209-9`, `FAR 52.222-37`, `FAR 52.204-10`, `FAR 52.204-30 Alternate
1`, `DFARS 252.216-7002`. Also `GSAM/R 552.242-99` and `GSAM/R 552.203-71` — a **fourth naming variant**
("GSAM/R", distinct from "GSAR") appears in at least two places; likely the same GSA regulation family
referred to inconsistently by the source document itself (worth normalizing both to one canonical family
label during extraction, not treating as different regulations).

**None of these incidental citations should land in the Clauses sheet.** They belong in FAR References
(or a DFARS-References-equivalent, if the DFARS sheet is meant to also separate incorporated-vs-incidental
the way FAR does — the ground-truth workbook's DFARS sheet has no incidental-reference counterpart sheet,
another open question for the gap analysis).

## Root cause of the screenshot's bad fields (confirmed against actual page content)

All four confirmed by direct text inspection — not inferred:

| Screenshot value | Actual source | Root cause |
|---|---|---|
| `Solicitation Number = "whether or not Contractors"` | Real Solicitation Number is `47QRCA23R0001` (page 2, SF33 Item 3). The phrase "whether or not Contractors" is body prose on **page 12-13** ("The OCO should indicate in the task order solicitation whether or not Contractors shall submit labor pricing...", section B.8.1) — a completely different page, completely unrelated sentence, that merely contains the word "solicitation." | The candidate generator is matching on keyword co-occurrence anywhere in the document rather than confining the search to the actual SF33 form-field region (page 2) and its correct spatial value. No page-locality constraint on this field. |
| `NAICS -> "Codes"` | Real NAICS handling is per-Domain (see CLINs/Contract Summary above). `"Codes"` is literally the trailing word of TOC entries like `"C.2.1.1 Management and Advisory Domain NAICS Codes....................18"` (page 6, Table of Contents) | TOC-heading contamination: the word "NAICS" inside a section-heading title (not a real field label) is being matched as a label, with the rest of that same heading line captured as its "value." |
| `B.8 -> "1 CONUS Standardized Labor Categories"` | Real section is `B.8 LABOR CATEGORIES` (page 11 per TOC); the value shown is actually the **next TOC line's tail**: `"B.8.1 CONUS Standardized Labor Categories.....11"` (page 6) with the subsection number's final digit (`.1`) misparsed as leading value text (`"1 CONUS..."`) | Subsection numbering (`B.8.1`) is being incorrectly split as key=`B.8` + value=`".1 CONUS..."` — a regex boundary error on multi-level section numbers, not a semantic extraction at all. Same root cause as the C.1/F.4/F.5 rows below. |
| `C.1 -> "1 North American Industry Classification System"` | TOC line `"C.1.1 North American Industry Classification System....16"` (page 6) | Identical subsection-number-splitting bug as above. |
| `F.4 -> "1 Deliverable and Reporting Requirements"` | TOC line `"F.4.1 Deliverable and Reporting Requirements....32"` (page 7) | Identical bug. |
| `Amount -> "$0.00"` | Real, correct, source-supported `Obligated Amount: $0.00` per CLIN (page 3) | **Not a bug in the value.** Bug is presentation: surfaced as an orphan scalar with no CLIN/description context instead of a CLIN-table column. |
| `Adm 4800` | Real text: `"...GSA Order ADM 4800.2I, Eligibility to Use GSA Sources of Supply and Service as amended."` (page 17, Section C.1 SCOPE) | Genuine narrative sentence referencing a GSA internal policy order (not FAR/DFARS/GSAR, a fourth citation family: GSA internal orders). Being surfaced as a bare scalar field ("Adm 4800" as if it were a label) instead of being left as narrative or routed to a general "policy reference" bucket. Not a business field at all. |
| `FAR -> "TITLE and DATE"` | Not independently verified in this pass — pattern consistent with the TOC/heading-contamination family above (a literal column-header string `"TITLE"`/`"DATE"` from some tabular content, e.g. the Section I clause list's own formatting, being captured as if it were a value) | Same family of bug: structural/tabular scaffolding text (headers, TOC lines) leaking into the kv_* candidate pool. Confirm exact source line when implementation begins; not blocking the diagnosis, which is already conclusively a structural-heading contamination problem, not a semantic extraction accuracy problem. |

**Summary of the actual defect class**: every one of the screenshot's bad rows is *structural contamination*
(Table of Contents lines, section-numbering artifacts, tabular column headers) reaching the business-field
candidate pool — not the discovery pipeline being "wrong" about semantic content. This matches the P0
prompt's own framing (section 3: reverse the pipeline so structure detection happens before candidate
classification) and is consistent with, but evidently incomplete relative to, prior fix attempts referenced
in this repo's git history (commit `5492415`, "reject TOC/dotted-leader and clause-citation values at
discovery") — that fix apparently catches dot-leader TOC lines but not TOC lines without trailing dot
leaders in this exact rendering, and does not catch the multi-level-subsection-number-splitting bug at all.
