"""V3 CLINs builder (docs/v3-schema-manifest.md §2).

Consumes `ParsedClinRow` directly (from `clin_block_detector.parse_clin_rows`,
via `v3_pipeline.classify_document`'s `clin_rows` field) rather than the
flattened `ClassifiedCandidate` stream — the CLIN candidate/routing step
only preserves `clin`/`amount` for dedup-with-Funding purposes; the richer
per-column fields (description, unit, PSC, base/option, ...) live on the
`ParsedClinRow` itself and would be lost by round-tripping through
`ClassifiedCandidate`.

Per v3-implementation-plan.md decision #1: no V3 schema change for the
CLIN/SLIN hierarchy — every row is independently exported with all 19
ground-truth columns; `parent_line_item`/`relationship` are internal-only
columns on `DocumentLineItem`, never surfaced as an extra V3 column.

Columns with no extraction logic yet (FOB, Purchase Request, POP Start/End,
Ship To, DODAAC, Status) stay blank rather than guessed — matches the
regression contract's actual shape (this base-IDIQ pricing schedule states
none of these per-CLIN; they are legitimately blank, not a bug).
"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_line_item import DocumentLineItem
from app.services.clin_block_detector import ParsedClinRow


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if not cleaned or cleaned.upper() in {"UNDEFINED", "NSP", "N/A"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def build_clins(
    *, document: Document, clin_rows: list[ParsedClinRow]
) -> list[DocumentLineItem]:
    rows: list[DocumentLineItem] = []
    for index, row in enumerate(clin_rows):
        qa_status = (
            "Verified" if row.confidence >= 0.7 else "Needs Review"
        )
        max_quantity_text = row.quantity if row.quantity else None

        rows.append(
            DocumentLineItem(
                document_id=document.id,
                row_index=index,
                clin=row.clin,
                description=row.description or "",
                quantity=_to_float(row.quantity),
                unit=row.unit,
                unit_price=_to_float(row.unit_price),
                amount=_to_float(row.amount),
                is_maximum=False,
                option_base=row.base_option,
                pricing_type=row.pricing_arrangement,
                max_quantity_text=max_quantity_text,
                psc=row.psc,
                qa_status=qa_status,
                slin=row.clin if row.parent_line_item else None,
                parent_line_item=row.parent_line_item,
                relationship=row.relationship,
                confidence=row.confidence,
                evidence_json={
                    "page_number": row.page_number,
                    "source_text": row.source_text,
                    "reason_codes": row.reason_codes,
                },
            )
        )
    return rows


def persist_clins(
    *, database: Session, document_id: str, rows: list[DocumentLineItem]
) -> None:
    database.execute(
        delete(DocumentLineItem).where(DocumentLineItem.document_id == document_id)
    )
    for row in rows:
        database.add(row)
