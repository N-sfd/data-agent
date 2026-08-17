import re
from typing import Any

from app.models.document_metadata_field import DocumentMetadataField
from app.services.contract_field_schema import (
    NUMERIC_FIELD_KEYS,
    RENEWAL_FIELD_KEYS,
)

NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*\.?\d*")
INTEGER_PATTERN = re.compile(r"\d+")


def _parse_number(raw_value: str) -> float | None:
    match = NUMBER_PATTERN.search(raw_value)

    if not match:
        return None

    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_int(raw_value: str) -> int | None:
    match = INTEGER_PATTERN.search(raw_value)

    if not match:
        return None

    return int(match.group(0))


def _renewal_type(raw_value: str) -> str | None:
    lowered = raw_value.lower()

    if "auto" in lowered:
        return "automatic"

    if raw_value.strip():
        return "manual"

    return None


def build_structured_output(
    fields: list[DocumentMetadataField],
) -> dict[str, Any]:
    """
    Every resolved field becomes a top-level key by its field_key,
    typed appropriately (numeric fields as numbers). The three
    renewal-related fields are pulled into a nested "renewal" object
    instead of appearing as flat keys. Unresolved fields are simply
    absent — never padded with nulls.
    """

    by_key = {field.field_key: field for field in fields}
    output: dict[str, Any] = {}

    for field in fields:
        if field.field_key in RENEWAL_FIELD_KEYS:
            continue

        if field.field_key in NUMERIC_FIELD_KEYS:
            number = _parse_number(field.value)
            output[field.field_key] = (
                number if number is not None else field.value
            )
        else:
            output[field.field_key] = field.value

    renewal: dict[str, Any] = {}

    auto_renewal = by_key.get("auto_renewal")
    if auto_renewal is not None:
        renewal["type"] = _renewal_type(auto_renewal.value)

    renewal_period = by_key.get("renewal_period")
    if renewal_period is not None:
        renewal["period_months"] = _parse_int(renewal_period.value)

    termination_notice = by_key.get("termination_notice")
    if termination_notice is not None:
        renewal["notice_days"] = _parse_int(termination_notice.value)

    if renewal:
        output["renewal"] = renewal

    return output
