import re
from uuid import uuid4

from app.models.document_page import DocumentPage
from app.schemas.contract_tables import NormalizedTable, RateCardRow

ROLE_HEADER_KEYWORDS = ("role", "title", "position", "resource")
RATE_HEADER_KEYWORDS = ("rate", "price", "fee", "cost")

RATE_CELL_PATTERN = re.compile(
    r"\$?\s*([\d,]+\.?\d*)\s*(?:/|per)?\s*"
    r"(hour|hr|hrs|hours|day|days|month|months|year|yr|yrs|years)?",
    re.IGNORECASE,
)

UNIT_NORMALIZATION: dict[str, str] = {
    "hr": "hour",
    "hrs": "hour",
    "hour": "hour",
    "hours": "hour",
    "day": "day",
    "days": "day",
    "month": "month",
    "months": "month",
    "year": "year",
    "yr": "year",
    "yrs": "year",
    "years": "year",
}


def _find_column(
    headers: list[str], keywords: tuple[str, ...]
) -> int | None:
    for index, header in enumerate(headers):
        lowered = header.lower()

        if any(keyword in lowered for keyword in keywords):
            return index

    return None


def _parse_rate_cell(
    raw: str,
) -> tuple[float | None, str | None, str | None]:
    match = RATE_CELL_PATTERN.search(raw)

    if not match or not match.group(1):
        return None, None, None

    try:
        rate = float(match.group(1).replace(",", ""))
    except ValueError:
        return None, None, None

    unit_text = match.group(2)
    unit = (
        UNIT_NORMALIZATION.get(unit_text.lower())
        if unit_text
        else None
    )
    currency = "USD" if "$" in raw else None

    return rate, unit, currency


def normalize_document_tables(
    pages: list[DocumentPage], document_name: str
) -> list[NormalizedTable]:
    normalized: list[NormalizedTable] = []

    for page in pages:
        raw_tables = page.tables_json or []

        for raw_table in raw_tables:
            headers: list[str] = raw_table.get("headers", [])
            rows: list[dict] = raw_table.get("rows", [])
            table_id = raw_table.get("table_id", str(uuid4()))

            source_reference = (
                f"{document_name}, page {page.page_number}"
            )

            role_index = _find_column(headers, ROLE_HEADER_KEYWORDS)
            rate_index = _find_column(headers, RATE_HEADER_KEYWORDS)

            if role_index is not None and rate_index is not None:
                role_header = headers[role_index]
                rate_header = headers[rate_index]

                rate_card_rows: list[RateCardRow] = []

                for row in rows:
                    role_value = str(
                        row.get(role_header, "")
                    ).strip()
                    rate_raw = str(
                        row.get(rate_header, "")
                    ).strip()

                    if not role_value or not rate_raw:
                        continue

                    rate, unit, currency = _parse_rate_cell(
                        rate_raw
                    )

                    rate_card_rows.append(
                        RateCardRow(
                            role=role_value,
                            rate=rate,
                            unit=unit,
                            currency=currency,
                        )
                    )

                if rate_card_rows:
                    normalized.append(
                        NormalizedTable(
                            table_id=table_id,
                            table_type="rate_card",
                            page_number=page.page_number,
                            source_reference=source_reference,
                            headers=headers,
                            rows=rows,
                            rate_card_rows=rate_card_rows,
                        )
                    )
                    continue

            normalized.append(
                NormalizedTable(
                    table_id=table_id,
                    table_type="generic",
                    page_number=page.page_number,
                    source_reference=source_reference,
                    headers=headers,
                    rows=rows,
                    rate_card_rows=[],
                )
            )

    return normalized
