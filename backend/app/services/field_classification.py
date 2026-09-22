"""Classify metadata/discovery fields for the canonical workbook dataset.

Business fields enter normalized.fields / All Fields / Key Contract Fields.
Narrative auto-kv keys and section markers stay out of that record and can
surface under Sections when needed.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.label_rejection import looks_like_narrative_fragment

# Canonical keys for the Key Contract Fields horizontal record.
KEY_CONTRACT_FIELD_KEYS: tuple[str, ...] = (
    "contract_number",
    "solicitation_number",
    "award_date",
    "contractor_name",
    "contractor",
    "ueid",
    "uei",
    "type_of_solicitation",
    "date_issued",
    "issued_by",
    "effective_date",
    "expiration_date",
    "total_value",
    "contract_value",
    "naics_code",
    "cage_code",
)

_KEY_CONTRACT_LABEL_HINTS = re.compile(
    r"\b("
    r"contract\s*(no\.?|number|#)|"
    r"solicitation|"
    r"award\s*date|"
    r"contractor|"
    r"uei[d]?|"
    r"type of solicitation|"
    r"date issued|"
    r"issued by|"
    r"effective date|"
    r"expiration|"
    r"total\s*(value|amount)|"
    r"naics|"
    r"cage"
    r")\b",
    re.IGNORECASE,
)

_KV_PREFIX = re.compile(r"^kv_", re.IGNORECASE)
_SECTION_KEY = re.compile(
    r"^(section|clause|article|sow|pws)_",
    re.IGNORECASE,
)
_SECTION_HEADING_LEADER = re.compile(
    r"^\s*(?:[A-Z]|\d{1,2})(?:\.\d{1,2})?\.?\s+"
)
_SECTION_HEADING_WORDS = frozenset(
    {
        "general", "authority", "background", "scope", "purpose",
        "applicability", "definitions", "references", "overview",
        "introduction", "objective", "objectives", "requirements",
        "responsibilities", "summary", "policy", "procedures",
        "total solution", "period of performance", "abbreviations",
        "acronyms", "applicable documents", "description", "discussion",
    }
)
_LONG_VALUE_CHARS = 160
_SOW_KV_SLUG = re.compile(
    r"^[a-z](_\d+)?_(general|authority|scope|background|name|total_solution)$",
    re.IGNORECASE,
)


def is_auto_kv_key(key: str | None) -> bool:
    return bool(key and _KV_PREFIX.match(key.strip()))


def _looks_like_section_heading(label: str) -> bool:
    stripped = _SECTION_HEADING_LEADER.sub("", label).strip().lower()
    return stripped in _SECTION_HEADING_WORDS


def is_key_contract_field(*, key: str | None, label: str | None = None) -> bool:
    normalized = (key or "").strip().lower()
    if normalized in KEY_CONTRACT_FIELD_KEYS:
        return True
    if normalized.startswith("kv_") and normalized[3:] in KEY_CONTRACT_FIELD_KEYS:
        return True
    haystack = f"{key or ''} {label or ''}"
    return bool(_KEY_CONTRACT_LABEL_HINTS.search(haystack))


def is_narrative_or_section_field(
    *,
    key: str | None,
    label: str | None = None,
    value: Any = None,
    field_group: str | None = None,
) -> bool:
    """True when a row must NOT enter normalized.fields / All Fields."""

    group = (field_group or "").strip().lower()
    if group in {"section", "clause", "narrative", "obligation"}:
        return True

    key_text = (key or "").strip()
    label_text = (label or "").strip() or key_text

    if _SECTION_KEY.match(key_text):
        return True
    if _looks_like_section_heading(label_text):
        return True
    if looks_like_narrative_fragment(label_text):
        return True

    value_text = "" if value is None else str(value).strip()
    if is_auto_kv_key(key_text):
        if len(value_text) >= _LONG_VALUE_CHARS:
            return True
        if looks_like_narrative_fragment(value_text):
            return True
        slug = key_text[3:]
        if _SOW_KV_SLUG.match(slug) and (len(value_text) >= 40 or not value_text):
            return True
        return False

    if len(value_text) >= _LONG_VALUE_CHARS and looks_like_narrative_fragment(
        value_text
    ):
        return True

    return False


def is_canonical_business_field(
    *,
    key: str | None,
    label: str | None = None,
    value: Any = None,
    field_group: str | None = None,
) -> bool:
    return not is_narrative_or_section_field(
        key=key, label=label, value=value, field_group=field_group
    )


def classify_workbook_bucket(
    *,
    key: str | None,
    label: str | None = None,
    value: Any = None,
    field_group: str | None = None,
    needs_review: bool = False,
) -> str:
    """Return one of: key_contract | field | section | needs_review."""

    if needs_review:
        return "needs_review"
    if is_narrative_or_section_field(
        key=key, label=label, value=value, field_group=field_group
    ):
        return "section"
    if is_key_contract_field(key=key, label=label):
        return "key_contract"
    return "field"
