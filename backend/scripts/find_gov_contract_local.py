"""Find local scanned gov-contract documents and run extraction demo."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "uploads"


def search_dbs() -> list[tuple[str, str, str, str]]:
    hits: list[tuple[str, str, str, str]] = []
    for db_name in ("data_agent.db", "data_agent_v2.db", "test_data_agent.db"):
        db_path = ROOT / db_name
        if not db_path.exists():
            continue
        con = sqlite3.connect(db_path)
        try:
            rows = con.execute(
                """
                SELECT d.id, d.original_filename, d.stored_filename, ?
                FROM documents d
                JOIN document_pages p ON p.document_id = d.id
                WHERE p.final_text LIKE '%47QRCA25DSF07%'
                   OR p.final_text LIKE '%SOLICITATION NUMBER%'
                GROUP BY d.id
                LIMIT 15
                """,
                (db_name,),
            ).fetchall()
            hits.extend(rows)
        except Exception as exc:  # noqa: BLE001
            print(f"{db_name}: {exc}")
        finally:
            con.close()
    return hits


def main() -> None:
    hits = search_dbs()
    print(f"db hits: {len(hits)}")
    for row in hits:
        print(" ", row)
        stored = UPLOADS / row[2]
        print("   exists=", stored.exists(), "path=", stored)


if __name__ == "__main__":
    main()
