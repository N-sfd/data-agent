"""One-off ingestion of reference/schemas/part_52_FAR_Master_FINAL.xlsx into
the far_master_clauses table (docs/far-master-schema-manifest.md). Read-only
reference data — safe to re-run (delete-then-insert), never touches
contract-derived data.

Usage: python backend/scripts/ingest_far_master.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import openpyxl  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.models.far_master_clause import FarMasterClause  # noqa: E402

XLSX_PATH = BACKEND_ROOT.parent / "reference" / "schemas" / "part_52_FAR_Master_FINAL.xlsx"

# Header row is row 3 (row 1 = merged title banner, row 2 blank) — confirmed
# by direct inspection, matches every other sheet in this workbook family.
HEADER_ROW = 3


def _clause_title_from_display(number: str, display_title: str | None) -> str | None:
    if not display_title:
        return None
    prefix = f"{number} "
    if display_title.startswith(prefix):
        return display_title[len(prefix):].strip() or None
    return display_title.strip() or None


def main() -> None:
    workbook = openpyxl.load_workbook(str(XLSX_PATH), read_only=True, data_only=True)
    sheet = workbook["FAR Master"]

    rows = list(sheet.iter_rows(min_row=HEADER_ROW, values_only=True))
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    index = {name: pos for pos, name in enumerate(headers)}

    required = [
        "FAR Record ID",
        "FAR Number",
        "Official Display Title",
        "Record Type",
        "Effective Date",
        "Prescribed In",
        "Alternates",
    ]
    missing = [name for name in required if name not in index]
    if missing:
        raise RuntimeError(f"FAR Master sheet missing expected columns: {missing}")

    records: list[FarMasterClause] = []
    seen_numbers: set[str] = set()
    for row in rows[1:]:
        far_number = row[index["FAR Number"]]
        if far_number is None:
            continue
        far_number = str(far_number).strip()
        if not far_number or far_number in seen_numbers:
            continue
        seen_numbers.add(far_number)

        display_title = row[index["Official Display Title"]]
        display_title = str(display_title).strip() if display_title is not None else ""
        record_type = row[index["Record Type"]]
        record_type = str(record_type).strip() if record_type is not None else ""
        effective_date = row[index["Effective Date"]]
        prescribed_in = row[index["Prescribed In"]]
        alternates = row[index["Alternates"]]

        records.append(
            FarMasterClause(
                far_number=far_number,
                far_record_id=str(row[index["FAR Record ID"]] or "").strip(),
                official_display_title=display_title,
                record_type=record_type,
                effective_date=(str(effective_date).strip() if effective_date else None),
                prescribed_in=(str(prescribed_in).strip() if prescribed_in else None),
                has_alternates=bool(alternates),
                clause_title=_clause_title_from_display(far_number, display_title),
            )
        )

    clause_count = sum(1 for r in records if r.record_type == "Clause")

    database = SessionLocal()
    try:
        database.execute(delete(FarMasterClause))
        database.add_all(records)
        database.commit()
    finally:
        database.close()

    print(f"Ingested {len(records)} FAR Master records from {XLSX_PATH.name}")
    print(f"  Record Type == 'Clause': {clause_count}")


if __name__ == "__main__":
    main()
