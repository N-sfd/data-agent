"""Oracle Output Mapping — adapter specification for the canonical FAR
model. It maps canonical fields to Oracle OUTPUT CONCEPTS only: no
release-specific import headers, XML elements or REST attribute names are
invented here. Exact target names are bound when the Oracle Fusion target
template/schema is supplied. This is not a final Oracle import file.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.far.canonical import ALTERNATE, CLAUSE_OR_PROVISION, RESERVED, SUBPART

TITLE = "Oracle Output Mapping — Adapter Specification"
NOTICE = (
    "Maps canonical FAR data to Oracle output concepts without inventing release-specific "
    "import headers. Exact XML/CSV/REST field names are bound when the target Oracle Fusion "
    "import template/schema is supplied. This is not a final Oracle import file."
)

READY = "READY"
REQUIRES_TEMPLATE = "REQUIRES ORACLE TEMPLATE"
PENDING_TEMPLATE = "PENDING TARGET TEMPLATE"


@dataclass(frozen=True)
class OutputMapRow:
    canonical_field: str
    purpose: str
    oracle_concept: str
    rule: str
    load_condition: str
    source_field: str
    example: str
    status: str


OUTPUT_MAP: tuple[OutputMapRow, ...] = (
    OutputMapRow("Clause Key", "Stable unique key for transformations", "External/source identifier",
                 "Generate stable FAR-based key; keep unchanged across re-runs.", "Load-eligible records",
                 "06_CANONICAL_MODEL!Clause Key", "FAR-52.204-3", READY),
    OutputMapRow("FAR Number", "Government clause/provision identifier", "Clause/provision reference or source attribute",
                 "Preserve exactly from FAR source.", "Load-eligible records",
                 "06_CANONICAL_MODEL!FAR Number", "52.204-3", READY),
    OutputMapRow("Display Name", "Human-readable clause/provision name", "Clause title/name",
                 "Use FAR # + Title for traceable display; Oracle-specific length rules applied only in output adapter.",
                 "Load-eligible records", "06_CANONICAL_MODEL!Display Name", "52.204-3 Taxpayer Identification", READY),
    OutputMapRow("Version Date", "Source revision/version date", "Clause version/date attribute",
                 "Normalize Month YYYY when available; do not invent missing dates.", "When source date exists",
                 "06_CANONICAL_MODEL!Version Date", "Oct 1998", READY),
    OutputMapRow("Content Type", "Controls routing and exclusions", "Output routing / record classification",
                 "CLAUSE_OR_PROVISION routes to load; RESERVED/SUBPART excluded; ALTERNATE records require variant handling.",
                 "All records", "06_CANONICAL_MODEL!Content Type", "CLAUSE_OR_PROVISION", READY),
    OutputMapRow("Source Text", "Canonical grouped FAR text", "Clause/provision text",
                 "Preserve grouped (a)/(b)/(1)/(i) hierarchy. Convert to Oracle-required XML/HTML/text only in final adapter.",
                 "Load-eligible records", "06_CANONICAL_MODEL!Source Text", "(a) ... (b) ...", READY),
    OutputMapRow("Prescription Reference", "Traceability to prescribing FAR section", "Source/reference metadata",
                 "Extract reference from 'As prescribed in ...'; retain even if target import template has no direct field.",
                 "When present", "06_CANONICAL_MODEL!Prescription Reference", "4.905", READY),
    OutputMapRow("Alternate Code", "Identifies alternate variant", "Alternate/variant relationship",
                 "Populate only from a structural Alternate I/II/etc. heading, not from narrative/example mentions. "
                 "Map the confirmed alternate to its basic clause relationship in the Oracle-specific output layer.",
                 "When alternate exists", "06_CANONICAL_MODEL!Alternate Code", "Alternate I", REQUIRES_TEMPLATE),
    OutputMapRow("Basic Clause Key", "Links alternate-bearing content to base record", "Parent/basic clause relationship",
                 "Use stable canonical key; final Oracle relationship fields depend on target interface/template.",
                 "When alternate exists", "06_CANONICAL_MODEL!Basic Clause Key", "FAR-52.215-1", REQUIRES_TEMPLATE),
    OutputMapRow("Embedded FAR References", "Cross-reference index only", "Reference metadata / transformation aid",
                 "Do not generate additional clause records from embedded references; use for validation/search/linking.",
                 "When present", "06_CANONICAL_MODEL!Embedded FAR References", "52.207-4; 52.209-1", READY),
    OutputMapRow("Load Eligible", "Prevents structural/reserved rows from being exported", "Output filter",
                 "Export only YES to clause/provision payload unless a target process explicitly requires structural metadata.",
                 "All records", "06_CANONICAL_MODEL!Load Eligible", "YES", READY),
    OutputMapRow("Oracle Payload", "Final system-specific payload", "XML / CSV / REST payload",
                 "Generate only after exact Oracle Fusion release, target object, and supported import template/schema are selected.",
                 "Final output stage", "Derived from canonical model", "Target-specific", PENDING_TEMPLATE),
)


def record_routing(content_type: str) -> tuple[str, str]:
    """(Oracle Target concept, Load / Mapping Status) of one canonical
    record — the 02_ORACLE_MAPPING view."""

    if content_type == CLAUSE_OR_PROVISION:
        return "Enterprise Contracts Clause / Provision", "MAP"
    if content_type == RESERVED:
        return "Reserved Marker", "SKIP / retain for source completeness"
    if content_type == SUBPART:
        return "Structural Heading", "REFERENCE / do not load as clause"
    if content_type == ALTERNATE:
        return "Clause / Provision alternate (variant of basic clause)", f"HOLD / {REQUIRES_TEMPLATE}"
    return "Unclassified", "REVIEW"
