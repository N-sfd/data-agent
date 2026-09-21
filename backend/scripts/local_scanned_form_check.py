"""Service-level local check for Contract_47QRCA25DSF07 (no HTTP upload)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.core.config import get_settings
from app.database.migrate import (
    ensure_detected_target_columns,
    ensure_document_metadata_field_columns,
    ensure_document_page_columns,
    ensure_documents_columns,
    ensure_extraction_model_columns,
    ensure_metadata_field_audit_log_columns,
    ensure_target_correction_columns,
)
from app.database.session import SessionLocal, engine
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services.ai_provider import DisabledAIProvider
from app.services.detected_target_store import load_document_targets
from app.services.document_extraction import process_document_pages
from app.services.schema_discovery import discover_document_schema
from app.services.target_extraction_service import extract_by_targets

DOC_ID = "8d907c3b-7bab-4516-8695-e82a90baa594"
PDF = ROOT / "uploads" / f"{DOC_ID}.pdf"
FOCUS_TOKENS = (
    "solicitation",
    "contract",
    "date issued",
    "date_issued",
    "issued by",
    "issued_by",
    "effective",
    "type of solicitation",
    "type_of_solicitation",
)
BAD_LABEL_FRAGMENTS = (
    "A. NAME",
    "B. TELEPHONE",
    "SOLICITATION NUMBER",
    "TYPE OF SOLICITATION",
    "DATE ISSUED",
    "REQUISITION",
    "ADDRESS OFFER",
    "Current as of Modification",
    "of any change to the CAF",
)


def _patch_schema() -> None:
    ensure_document_page_columns(engine)
    ensure_documents_columns(engine)
    ensure_document_metadata_field_columns(engine)
    ensure_extraction_model_columns(engine)
    ensure_target_correction_columns(engine)
    ensure_metadata_field_audit_log_columns(engine)
    ensure_detected_target_columns(engine)


async def _run() -> None:
    _patch_schema()
    settings = get_settings()
    if not PDF.exists():
        raise SystemExit(f"Missing PDF: {PDF}")

    database = SessionLocal()
    try:
        document = database.get(Document, DOC_ID)
        if document is None:
            raise SystemExit(f"Document {DOC_ID} not in DB")

        print("=== Local scanned-form extraction check ===")
        print(f"document: {document.original_filename}")
        print(f"id: {DOC_ID}")
        print(f"pdf: {PDF} ({PDF.stat().st_size} bytes)")

        summary = process_document_pages(
            database=database,
            document_record=document,
            file_path=PDF,
            settings=settings,
            run_ocr=True,
            page_start=1,
            page_end=3,
            force_reprocess=True,
        )
        print(
            "extract-pages",
            "processed=",
            summary.get("pages_processed"),
            "ocr_required=",
            summary.get("ocr_required_pages"),
            "ocr_ok=",
            summary.get("ocr_completed_pages"),
        )

        pages = list(
            database.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == DOC_ID)
                .order_by(DocumentPage.page_number)
            )
        )
        for page in pages[:3]:
            layout = getattr(page, "ocr_layout_json", None)
            print(
                f"  page {page.page_number}: chars={len(page.final_text or '')} "
                f"ocr={page.ocr_succeeded} scanned={page.is_scanned} "
                f"method={page.extraction_method} "
                f"layout_words="
                f"{len((layout or {}).get('words') or []) if layout else 0}"
            )
            preview = (page.final_text or "").replace("\n", " | ")[:220]
            print(f"    text preview: {preview}")

        discovery = await discover_document_schema(
            document=document,
            pages=pages,
            ai_provider=DisabledAIProvider(),
        )
        targets = discovery.targets
        print(f"discovered targets: {len(targets)}")

        selected = [
            t
            for t in targets
            if any(
                tok in f"{t.key} {t.label} {t.display_name or ''}".lower()
                for tok in FOCUS_TOKENS
            )
        ]
        if not selected:
            selected = targets[:30]
        print("selected:")
        for target in selected:
            print(f"  - {target.key}: {target.display_name or target.label}")

        from app.services.detected_target_store import persist_document_targets

        persist_document_targets(database=database, result=discovery)
        database.commit()

        result = await extract_by_targets(
            database=database,
            document=document,
            target_ids=[t.id for t in selected],
            use_ai_fallback=False,
            ai_provider=DisabledAIProvider(),
        )

        print("\nFIELD                          VALUE")
        print("-" * 92)
        failures = []
        for item in result.scalars:
            value = item.value
            display = "(Needs Review / null)" if value in (None, "") else str(value)
            if len(display) > 72:
                display = display[:69] + "..."
            components = (
                item.confidence_detail.components.model_dump()
                if item.confidence_detail and item.confidence_detail.components
                else {}
            )
            print(f"{item.target:<30} {display}")
            print(
                f"{'':30} conf={item.confidence} band={item.confidence_band} "
                f"method={item.extraction_method} validation={item.validation_status} "
                f"review={item.review_status} "
                f"ocr={components.get('ocr')} final={components.get('final')}"
            )
            text = "" if value is None else str(value)
            if any(frag.lower() in text.lower() for frag in BAD_LABEL_FRAGMENTS):
                failures.append((item.target, text))

        print("\nTABLES")
        print("-" * 92)
        if not result.tables:
            print("(none in this selection)")
        for table in result.tables[:5]:
            print(
                f"{table.target}: {len(table.rows)} rows x {len(table.columns)} cols"
            )
            print(f"  headers={table.columns[:10]}")
            if table.rows:
                print(f"  row0={table.rows[0]}")

        print("\nunresolved:", result.unresolved_targets)
        print("warnings:", result.warnings[:5])

        print("\nGATE")
        print("-" * 92)
        if failures:
            print("FAIL — form labels still present as values:")
            for key, text in failures:
                print(f"  {key}: {text[:140]}")
            raise SystemExit(1)
        print("PASS — none of the known form-label mashups appear as scalar values.")
        print(f"Open UI after starting servers: /extraction/new?documentId={DOC_ID}")
    finally:
        database.close()


if __name__ == "__main__":
    asyncio.run(_run())
