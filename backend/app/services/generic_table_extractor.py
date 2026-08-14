from uuid import uuid4

import pdfplumber


def clean_cell(
    value: object,
) -> str:

    if value is None:
        return ""

    return " ".join(
        str(value)
        .replace("\n", " ")
        .split()
    )


def make_unique_headers(
    raw_headers: list[object],
) -> list[str]:

    used: dict[str, int] = {}
    headers: list[str] = []

    for index, value in enumerate(
        raw_headers
    ):

        base = clean_cell(value)

        if not base:
            base = f"Column {index + 1}"

        count = used.get(base, 0) + 1

        used[base] = count

        if count > 1:
            base = f"{base} ({count})"

        headers.append(base)

    return headers


def extract_page_tables(
    pdf_path,
    page_number: int,
) -> list[dict]:

    tables: list[dict] = []

    with pdfplumber.open(
        pdf_path
    ) as pdf:

        if (
            page_number < 1
            or page_number > len(pdf.pages)
        ):
            return []

        page = pdf.pages[
            page_number - 1
        ]

        raw_tables = (
            page.extract_tables()
            or []
        )

        for raw_table in raw_tables:

            if (
                not raw_table
                or len(raw_table) < 2
            ):
                continue

            headers = make_unique_headers(
                raw_table[0]
            )

            rows: list[dict] = []

            for raw_row in raw_table[1:]:

                if not raw_row:
                    continue

                values = [
                    clean_cell(value)
                    for value
                    in raw_row
                ]

                while len(values) < len(headers):
                    values.append("")

                row = {
                    headers[index]:
                        values[index]

                    for index in range(
                        len(headers)
                    )
                }

                if any(row.values()):
                    rows.append(row)

            if rows:

                tables.append(
                    {
                        "table_id":
                            str(uuid4()),

                        "headers":
                            headers,

                        "rows":
                            rows,
                    }
                )

    return tables