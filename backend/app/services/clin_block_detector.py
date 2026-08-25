import re
from dataclasses import dataclass

from app.models.document_page import DocumentPage

_CLIN_HEADER_KEYWORDS = (
    "clin",
    "item no",
    "item number",
    "line item",
)

_CLIN_NUMBER_PATTERN = re.compile(r"^\d{4}[A-Z]{0,2}$")


@dataclass(frozen=True)
class RepeatedRecordBlock:
    key: str
    label: str
    headers: list[str]
    row_count: int
    page_number: int


def _row_first_value(row: object) -> str | None:
    if isinstance(row, dict):
        values = list(row.values())
    elif isinstance(row, (list, tuple)):
        values = list(row)
    else:
        return None
    if not values:
        return None
    return str(values[0]).strip()


def detect_repeated_records(
    *,
    page: DocumentPage,
) -> list[RepeatedRecordBlock]:
    blocks: list[RepeatedRecordBlock] = []

    for table in page.tables_json or []:
        headers = [str(h) for h in (table.get("headers") or [])]
        rows = table.get("rows") or []

        if len(rows) < 2:
            continue

        header_haystack = " ".join(headers).lower()
        header_hit = any(
            keyword in header_haystack for keyword in _CLIN_HEADER_KEYWORDS
        )

        clin_shaped_rows = sum(
            1
            for row in rows
            if (first := _row_first_value(row)) is not None
            and _CLIN_NUMBER_PATTERN.match(first)
        )
        value_hit = clin_shaped_rows >= 2

        if not (header_hit or value_hit):
            continue

        blocks.append(
            RepeatedRecordBlock(
                key="clin_schedule",
                label="CLIN Schedule",
                headers=headers,
                row_count=len(rows),
                page_number=page.page_number,
            )
        )

    return blocks
