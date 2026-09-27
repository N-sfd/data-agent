"""Neutral structural hints for a table's columns and rows.

These describe SHAPE only — "this column holds money-like amounts", "this
row is a total" — and never name the table ("invoice lines", "CLINs").
Profiles decide what a table means.
"""

from __future__ import annotations

import re

from app.source_structure.models import TableCandidate
from app.source_structure.text_shapes import infer_value_type

_TOTAL_ROW = re.compile(r"\b(sub\s*-?total|total|grand total|balance)\b", re.I)
_TWO_DECIMALS = re.compile(r"\d\.\d{2}\)?$")
_UNIT_TOKEN = re.compile(r"^[A-Za-z]{1,4}\.?$")


def _share(values: list[str], predicate) -> float:
    filled = [v for v in values if v]
    if not filled:
        return 0.0
    return sum(1 for v in filled if predicate(v)) / len(filled)


def annotate_table(table: TableCandidate) -> None:
    rows = [[cell.text for cell in row] for row in table.rows]
    total_rows = [
        index
        for index, row in enumerate(rows)
        if _TOTAL_ROW.search(" ".join(row)) and sum(1 for c in row if c) <= max(2, len(row) // 2)
    ]
    table.total_row_indices = total_rows
    body = [row for index, row in enumerate(rows) if index not in total_rows]
    columns = max((len(r) for r in body), default=0)

    hints: dict[int, list[str]] = {}
    word_counts: dict[int, float] = {}
    for c in range(columns):
        values = [row[c] if c < len(row) else "" for row in body]
        types = [infer_value_type(v) for v in values if v]
        column_hints: list[str] = []
        amount_share = _share(
            values, lambda v: infer_value_type(v) == "currency" or bool(_TWO_DECIMALS.search(v))
        )
        number_share = _share(values, lambda v: infer_value_type(v) == "number")
        if amount_share >= 0.6:
            column_hints.append("numeric_amount_column")
        elif number_share >= 0.6 and c > 0:
            column_hints.append("quantity_column")
        if types and sum(1 for t in types if t == "date") / len(types) >= 0.6:
            column_hints.append("date_column")
        filled = [v for v in values if v]
        if (
            c == 0
            and filled
            and len(set(filled)) == len(filled)
            and all(len(v.split()) <= 2 and len(v) <= 24 for v in filled)
        ):
            column_hints.append("identifier_column")
        if filled and _share(values, lambda v: bool(_UNIT_TOKEN.match(v))) >= 0.8 and len(set(filled)) < len(filled) + 1 and "identifier_column" not in column_hints:
            column_hints.append("unit_column")
        if column_hints:
            hints[c] = column_hints  # type: ignore[assignment]
        word_counts[c] = (
            sum(len(v.split()) for v in filled) / len(filled) if filled else 0.0
        )

    text_columns = [
        c
        for c in range(columns)
        if c not in hints and word_counts.get(c, 0) >= 1.5
    ]
    if text_columns:
        description = max(text_columns, key=lambda c: word_counts[c])
        hints.setdefault(description, []).append("description_column")  # type: ignore[arg-type]
    table.column_hints = hints  # type: ignore[assignment]

    patterns = [tuple(bool(c) for c in row) for row in body]
    if len(body) >= 2 and len(set(patterns)) <= max(1, len(body) // 2) and any(
        "numeric_amount_column" in h or "quantity_column" in h for h in hints.values()
    ):
        table.table_hints.append("repeating_records")
    if table.header_cells:
        table.table_hints.append("has_header_row")
    if total_rows:
        table.table_hints.append("has_total_row")
