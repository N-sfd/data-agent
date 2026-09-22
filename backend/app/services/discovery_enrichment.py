"""Schema-agnostic enrichment for discovered targets.

Normalization and grouping enhance discovery; they do not define the
schema. Unknown business fields still surface as selectable targets.
"""

from __future__ import annotations

import re

# Known aliases → canonical display names. Enhancement only — labels
# that never match still keep their polished form via format_display_label.
_DISPLAY_ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^solicitation\s*(no\.?|number|#)?$", re.I), "Solicitation Number"),
    (re.compile(r"^contract\s*(no\.?|number|#)?$", re.I), "Contract Number"),
    (re.compile(r"^requisition.*", re.I), "Requisition / Purchase Request Number"),
    (re.compile(r"^date\s+issued$", re.I), "Date Issued"),
    (re.compile(r"^effective\s+date$", re.I), "Effective Date"),
    (re.compile(r"^total\s+(contract\s+)?(value|amount)$", re.I), "Total Contract Value"),
    (re.compile(r"^unit\s+price$", re.I), "Unit Price"),
    (re.compile(r"^payment\s+terms$", re.I), "Payment Terms"),
]

_GROUP_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "Solicitation Metadata",
        ("solicitation", "offeror", "rfq", "rfp", "invitation"),
    ),
    (
        "Identifiers",
        (
            "contract no",
            "contract number",
            "requisition",
            "purchase request",
            "project no",
            "naics",
            "psc",
            "cage",
            "duns",
            "uei",
            "clin",
            "serial",
            "award number",
            "grant",
        ),
    ),
    ("Dates", ("date", "issued", "effective", "expir", "deadline", "due", "renewal")),
    (
        "Pricing",
        ("amount", "price", "total", "cost", "fee", "currency", "quantity", "qty"),
    ),
    (
        "Parties",
        ("vendor", "supplier", "customer", "contractor", "agency", "organization"),
    ),
    ("Contacts", ("email", "phone", "fax", "contact", "officer")),
    ("Addresses", ("address", "street", "city", "state", "zip", "postal")),
    ("Tables", ()),  # set via target_type
]


def canonical_display_name(label: str) -> str:
    cleaned = " ".join((label or "").split()).strip()
    if not cleaned:
        return cleaned
    for pattern, canonical in _DISPLAY_ALIASES:
        if pattern.match(cleaned.rstrip(":")):
            return canonical
    return cleaned


# Internal candidate-key prefixes that must never reach a display surface.
_INTERNAL_KEY_PREFIXES = ("kv_", "custom_", "section_", "table_", "field_")

# Short tokens that read better upper-cased than title-cased in a
# last-resort humanized label ("PR Number", not "Pr Number").
_ACRONYM_WORDS = frozenset(
    {
        "pr", "id", "uei", "ueid", "cage", "naics", "psc", "sow", "pws",
        "clin", "duns", "ssn", "ein", "po", "rfq", "rfp", "far", "dfars",
    }
)


def humanize_field_key(key: str | None) -> str:
    """Last-resort display text for a field with no resolved label.

    Never surfaces an internal discovery candidate key (``kv_pr_number``,
    ``custom_notes``, ...) verbatim — strips the internal prefix and
    title-cases the remaining slug instead of showing the raw key.
    """

    text = (key or "").strip()
    if not text:
        return "Untitled Field"
    lowered = text.lower()
    for prefix in _INTERNAL_KEY_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            break
    words = [word for word in re.split(r"[_\s]+", text) if word]
    if not words:
        return "Untitled Field"
    return " ".join(
        word.upper() if word.lower() in _ACRONYM_WORDS else word.capitalize()
        for word in words
    )


def assign_discovery_group(
    *,
    label: str,
    target_type: str,
) -> str:
    if target_type == "table":
        return "Tables"
    if target_type == "contact":
        return "Contacts"
    if target_type == "clause":
        return "Clauses"
    if target_type == "signature":
        return "Signatures"
    if target_type == "custom":
        return "Custom Fields"

    lowered = label.lower()
    for group, keywords in _GROUP_RULES:
        if group == "Tables":
            continue
        if any(keyword in lowered for keyword in keywords):
            return group

    if target_type == "date":
        return "Dates"
    if target_type == "amount":
        return "Pricing"
    if target_type == "identifier":
        return "Identifiers"

    return "Document Fields"


def infer_value_type(*, label: str, target_type: str) -> str:
    if target_type == "table":
        return "table"
    if target_type == "date":
        return "date"
    if target_type == "amount":
        return "currency"
    if target_type == "contact":
        lowered = label.lower()
        if "email" in lowered:
            return "email"
        if "phone" in lowered or "fax" in lowered:
            return "phone"
        return "string"
    if target_type == "identifier":
        return "identifier"
    return "string"


def method_from_evidence(evidence: list[str]) -> str | None:
    if not evidence:
        return None
    first = evidence[0]
    if "(" in first and first.endswith(")"):
        inner = first.rsplit("(", 1)[-1].rstrip(")")
        return inner.split(";", 1)[0].strip() or None
    return None


def labels_from_evidence(evidence: list[str], fallback_label: str) -> list[str]:
    labels: list[str] = []
    for item in evidence:
        if item.startswith("'") and ":" in item:
            raw = item[1:].split(":", 1)[0].strip()
            if raw and raw not in labels:
                labels.append(raw)
    if not labels and fallback_label:
        labels.append(fallback_label)
    return labels
