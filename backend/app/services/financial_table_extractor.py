from pathlib import Path
from uuid import uuid4

import pdfplumber

from app.schemas.financial_analysis import (
    FinancialTableResult,
)


def clean_value(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def make_unique_headers(
    headers: list[str],
) -> list[str]:
    result: list[str] = []
    counts: dict[str, int] = {}

    for index, header in enumerate(headers):
        name = header.strip()

        if not name:
            name = f"Column {index + 1}"

        count = counts.get(name, 0) + 1
        counts[name] = count

        if count > 1:
            name = f"{name} ({count})"

        result.append(name)

    return result


def extract_tables_from_pages(
    *,
    file_path: Path,
    original_filename: str,
    page_numbers: list[int],
) -> list[FinancialTableResult]:

    results: list[FinancialTableResult] = []

    with pdfplumber.open(file_path) as pdf:

        for page_number in page_numbers:

            if page_number < 1:
                continue

            if page_number > len(pdf.pages):
                continue

            page = pdf.pages[page_number - 1]

            raw_tables = page.extract_tables()

            for raw_table in raw_tables:

                if not raw_table:
                    continue

                if len(raw_table) < 2:
                    continue

                raw_headers = [
                    clean_value(value)
                    for value in raw_table[0]
                ]

                headers = make_unique_headers(
                    raw_headers
                )

                rows: list[dict[str, str]] = []

                for raw_row in raw_table[1:]:

                    if raw_row is None:
                        continue

                    values = [
                        clean_value(value)
                        for value in raw_row
                    ]

                    while len(values) < len(headers):
                        values.append("")

                    row = {
                        headers[index]: values[index]
                        for index in range(
                            len(headers)
                        )
                    }

                    if any(row.values()):
                        rows.append(row)

                if not rows:
                    continue

                results.append(
                    FinancialTableResult(
                        table_id=str(uuid4()),
                        page_number=page_number,
                        headers=headers,
                        rows=rows,
                        confidence=0.80,
                        source_reference=(
                            f"{original_filename}, "
                            f"page {page_number}"
                        ),
                        warnings=[],
                    )
                )

    return results