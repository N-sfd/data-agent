"""Build, store and load a document's contract structure (cover-form fields,
schedule tables, clauses). Built once — at staging preparation, or on first
read for documents processed before this existed — and stored as JSON."""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract_structure.clauses import read_clauses
from app.contract_structure.forms import read_cover_forms
from app.contract_structure.lines import PageLines, load_page_lines, strip_running_lines
from app.contract_structure.schedule import read_schedule_tables
from app.models.document import Document
from app.models.document_contract_structure import DocumentContractStructure

# Bump when extraction changes so stored structures are rebuilt.
EXTRACTOR_VERSION = 5


def build_contract_structure(database: Session, document: Document) -> dict:
    return structure_from_pages(load_page_lines(database, document))


def structure_from_pages(pages: list[PageLines]) -> dict:
    if not pages:
        return {"version": EXTRACTOR_VERSION, "fields": [], "tables": {}, "clauses": []}
    # Form pages are read before running headers are stripped: a cover
    # form's contract number repeats as the continuation pages' header.
    fields = read_cover_forms(pages)
    body = strip_running_lines(pages)
    tables = read_schedule_tables(body)
    clauses = read_clauses(body)
    return {
        "version": EXTRACTOR_VERSION,
        "fields": [asdict(field) for field in fields],
        "tables": {
            table.kind: {
                "columns": [{"key": column.key, "header": column.header} for column in table.columns],
                "records": [asdict(record) for record in table.records],
            }
            for table in tables
        },
        "clauses": [asdict(clause) for clause in clauses],
    }


def materialize_contract_structure(database: Session, document: Document) -> dict:
    payload = build_contract_structure(database, document)
    row = database.scalar(
        select(DocumentContractStructure).where(DocumentContractStructure.document_id == document.id)
    )
    if row is None:
        row = DocumentContractStructure(document_id=document.id, extractor_version=EXTRACTOR_VERSION, payload=payload)
        database.add(row)
    else:
        row.extractor_version = EXTRACTOR_VERSION
        row.payload = payload
    database.commit()
    return payload


def load_contract_structure(database: Session, document: Document) -> dict:
    """The stored structure, rebuilt when missing or from an older extractor."""
    row = database.scalar(
        select(DocumentContractStructure).where(DocumentContractStructure.document_id == document.id)
    )
    if row is not None and row.extractor_version == EXTRACTOR_VERSION:
        return row.payload
    return materialize_contract_structure(database, document)
