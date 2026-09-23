"""V3 Source Documents (docs/v3-schema-manifest.md §9) — computed at read
time from existing `Document` rows, per the gap analysis's own note that
this dataset is "mostly derivable" and doesn't need a new table. A
document's portfolio is itself (root) plus every `Document` row that shares
its root via `parent_document_id`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document

_ROLE_BY_RELATIONSHIP_TYPE = {
    "amendment_of": "Amendment",
    "change_order_of": "Change Order",
    "sow_of": "Statement of Work",
    "subcontract_of": "Subcontract",
}


@dataclass
class SourceDocumentRow:
    source_document: str
    role: str
    pages: int
    extraction_status: str


def _root_document_id(document: Document, database: Session) -> str:
    current = document
    seen: set[str] = set()
    while current.parent_document_id and current.parent_document_id not in seen:
        seen.add(current.id)
        parent = database.get(Document, current.parent_document_id)
        if parent is None:
            break
        current = parent
    return current.id


def build_source_documents(
    *, database: Session, document: Document
) -> list[SourceDocumentRow]:
    root_id = _root_document_id(document, database)

    portfolio = database.scalars(
        select(Document).where(
            (Document.id == root_id) | (Document.parent_document_id == root_id)
        )
    ).all()

    rows: list[SourceDocumentRow] = []
    for doc in portfolio:
        role = (
            "Primary award / contract"
            if doc.id == root_id
            else _ROLE_BY_RELATIONSHIP_TYPE.get(
                doc.parent_relationship_type or "", "Related document"
            )
        )
        status = "Extracted" if doc.processing_status == "completed" else "Pending"
        rows.append(
            SourceDocumentRow(
                source_document=doc.original_filename,
                role=role,
                pages=doc.page_count,
                extraction_status=status,
            )
        )
    return rows
