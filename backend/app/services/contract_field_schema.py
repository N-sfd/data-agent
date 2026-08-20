import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    group: str
    key: str
    label: str
    description: str | None = None
    data_type: str | None = None


# (group, [(field_key, field_label), ...])
_RAW_FIELD_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Identification",
        [
            ("contract_title", "Contract Title"),
            ("contract_number", "Contract Number"),
            ("contract_type", "Contract Type"),
            ("document_type", "Document Type"),
            ("contract_status", "Contract Status"),
            ("parent_contract", "Parent Contract"),
            ("version", "Version"),
        ],
    ),
    (
        "Parties",
        [
            ("supplier", "Supplier"),
            ("customer", "Customer"),
            ("legal_entity", "Legal Entity"),
            ("counterparty", "Counterparty"),
            ("party_address", "Party Address"),
            ("signatory", "Signatory"),
        ],
    ),
    (
        "Dates",
        [
            ("effective_date", "Effective Date"),
            ("execution_date", "Execution Date"),
            ("start_date", "Start Date"),
            ("end_date", "End Date"),
            ("expiration_date", "Expiration Date"),
            ("renewal_date", "Renewal Date"),
            ("notice_date", "Notice Date"),
            ("termination_date", "Termination Date"),
            ("award_date", "Award Date"),
        ],
    ),
    (
        "Financial",
        [
            ("contract_value", "Contract Value"),
            ("currency", "Currency"),
            ("payment_terms", "Payment Terms"),
            ("billing_frequency", "Billing Frequency"),
            ("pricing_model", "Pricing Model"),
            ("rate_card", "Rate Card"),
            ("price_escalation", "Price Escalation"),
            ("discount", "Discount"),
            ("late_fees", "Late Fees"),
        ],
    ),
    (
        "Legal",
        [
            ("governing_law", "Governing Law"),
            ("jurisdiction", "Jurisdiction"),
            ("liability_cap", "Liability Cap"),
            ("indemnification", "Indemnification"),
            ("confidentiality", "Confidentiality"),
            ("termination_rights", "Termination Rights"),
            ("force_majeure", "Force Majeure"),
            ("insurance", "Insurance"),
            ("assignment", "Assignment"),
            ("warranty", "Warranty"),
        ],
    ),
    (
        "Commercial",
        [
            ("auto_renewal", "Auto Renewal"),
            ("renewal_period", "Renewal Period"),
            ("termination_notice", "Termination Notice"),
            ("minimum_commitment", "Minimum Commitment"),
            ("volume_commitment", "Volume Commitment"),
            ("service_credits", "Service Credits"),
            ("fob", "FOB"),
        ],
    ),
    (
        "Compliance",
        [
            ("data_privacy", "Data Privacy"),
            ("security_requirements", "Security Requirements"),
            ("audit_rights", "Audit Rights"),
            ("regulatory_requirements", "Regulatory Requirements"),
            ("certifications", "Certifications"),
        ],
    ),
    (
        "Government",
        [
            ("solicitation_number", "Solicitation No."),
            ("purchase_request_number", "Purchase Request No."),
            ("proposal_number", "Proposal No."),
            ("facility_code", "Facility Code"),
            ("project_number", "Project No."),
            ("naics_code", "NAICS Code"),
            ("psc_code", "PSC Code"),
            ("contracting_officer", "Contracting Officer"),
            ("calendar_days", "Calendar Days"),
            ("zip_code", "ZIP Code"),
            ("time_and_date", "Time and Date"),
        ],
    ),
]


FIELD_SPECS: list[FieldSpec] = [
    FieldSpec(group=group, key=key, label=label)
    for group, fields in _RAW_FIELD_GROUPS
    for key, label in fields
]

# Fields whose extracted text should be normalized as a date.
DATE_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "effective_date",
        "execution_date",
        "start_date",
        "end_date",
        "expiration_date",
        "renewal_date",
        "notice_date",
        "termination_date",
        "award_date",
        "time_and_date",
    }
)

# Fields whose extracted text should be normalized as a money amount.
MONEY_FIELD_KEYS: frozenset[str] = frozenset({"contract_value"})

# Fields whose extracted text should be normalized against a fixed code
# pattern (e.g. NAICS/PSC/ZIP), analogous to MONEY_PATTERN for money fields.
CODE_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "naics_code": re.compile(r"\b\d{6}\b"),
    "psc_code": re.compile(r"\b[A-Z0-9]{4}\b"),
    "zip_code": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
}

# Fields whose value should be coerced to a number in structured output.
NUMERIC_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "contract_value",
        "liability_cap",
        "discount",
        "late_fees",
        "minimum_commitment",
        "volume_commitment",
        "calendar_days",
    }
)

# Fields grouped into a nested "renewal" object in structured output,
# instead of appearing as flat top-level keys.
RENEWAL_FIELD_KEYS: frozenset[str] = frozenset(
    {"auto_renewal", "renewal_period", "termination_notice"}
)


def field_spec_by_key(key: str) -> FieldSpec | None:
    for spec in FIELD_SPECS:
        if spec.key == key:
            return spec

    return None
