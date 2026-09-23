"""CLIN completeness diagnostic (quality-gate follow-up): for every
CLIN-shaped candidate row found in the regression contract, reports page,
detected identifier, row structure, and accept/reject reasoning - so a
missing/extra CLIN can be explained rather than guessed at.

Usage: python backend/scripts/clin_diagnostic_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.services.clin_block_detector import (  # noqa: E402
    _CLIN_HEADER_KEYWORDS,
    _CLIN_NUMBER_PATTERN,
    _row_first_value,
    _row_has_supporting_content,
    parse_clin_rows,
)

PDF_NAME_LIKE = "Contract_47QRCA%"


def main() -> None:
    database = SessionLocal()
    document = database.scalars(
        select(Document).where(Document.original_filename.like(PDF_NAME_LIKE))
    ).first()
    if document is None:
        print("Regression document not found — run generate_v3_workbook.py first.")
        return

    pages = list(
        database.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        )
    )

    print(f"{'PAGE':>4}  {'IDENTIFIER':10}  {'STRUCTURE':7}  {'STATUS':10}  REASON / ROW")
    print("-" * 100)

    accepted_total = 0
    rejected_total = 0

    for page in pages:
        # Every candidate 4-6 digit-shaped token in any detected table on
        # this page, whether or not it ends up accepted - full visibility
        # into what was considered and why.
        for table in page.tables_json or []:
            headers = [str(h) for h in (table.get("headers") or [])]
            rows = table.get("rows") or []
            header_haystack = " ".join(headers).lower()
            header_hit = any(k in header_haystack for k in _CLIN_HEADER_KEYWORDS)
            clin_shaped_count = sum(
                1
                for row in rows
                if (first := _row_first_value(row)) and _CLIN_NUMBER_PATTERN.match(first)
            )
            table_eligible = header_hit or clin_shaped_count >= 2

            for row in rows:
                first_value = _row_first_value(row)
                if not first_value or not _CLIN_NUMBER_PATTERN.match(first_value):
                    continue
                if not table_eligible:
                    rejected_total += 1
                    print(
                        f"{page.page_number:>4}  {first_value:10}  {'TABLE':7}  "
                        f"{'REJECTED':10}  table not CLIN-eligible "
                        f"(header_hit={header_hit}, clin_shaped_rows={clin_shaped_count}) row={row}"
                    )
                    continue
                if not _row_has_supporting_content(row, first_value):
                    rejected_total += 1
                    print(
                        f"{page.page_number:>4}  {first_value:10}  {'TABLE':7}  "
                        f"{'REJECTED':10}  no supporting content beyond bare number row={row}"
                    )
                    continue
                accepted_total += 1
                print(
                    f"{page.page_number:>4}  {first_value:10}  {'TABLE':7}  "
                    f"{'ACCEPTED':10}  row={row}"
                )

        # Text-fallback candidates (only reached in production when the
        # page had zero eligible tables — shown here for full visibility
        # regardless, since a text-shaped line can still exist alongside
        # an eligible table).
        import re

        for line in (page.final_text or "").splitlines():
            stripped = line.strip()
            match = re.match(r"^(\d{4,6}[A-Z]{0,2})\s{2,}\S", stripped)
            if not match:
                continue
            identifier = match.group(1)
            print(
                f"{page.page_number:>4}  {identifier:10}  {'TEXT':7}  "
                f"{'CANDIDATE':10}  line={stripped[:80]!r}"
            )

    print("-" * 100)
    print(f"Table-path accepted: {accepted_total} | rejected: {rejected_total}")

    print("\nFinal parse_clin_rows() output (table path preferred, text fallback only if empty):")
    total = 0
    for page in pages:
        for row in parse_clin_rows(page=page):
            total += 1
            print(f"  p{page.page_number}: {row.clin} desc={row.description!r} amount={row.amount!r}")
    print(f"\nTOTAL ACCEPTED CLIN ROWS: {total}")

    database.close()


if __name__ == "__main__":
    main()
