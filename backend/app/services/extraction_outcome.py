"""Resolves every processed document to one explicit, user-facing outcome so
Results is never a blank workbook.

    populated            records found, none flagged
    needs_review         records found, at least one flagged Needs Review
    no_supported_fields  extraction ran cleanly but found no supported values
    special_source       the visible pages aren't the real content (e.g. PDF
                         Portfolio) — says what to do instead
    failed               the canonical extraction stage raised
    pending              no extraction outcome recorded yet (job still running,
                         or a document processed before outcomes existed)

Computed at read time from the persisted datasets plus the `v3_extraction`
record the extraction job writes into `Document.ingestion_provenance`.
"""

from __future__ import annotations

from app.schemas.v3_document import ExtractionOutcome, NormalizedV3Document
from app.services.source_inspection import (
    SOURCE_KIND_PDF_EMBEDDED_FILES,
    SOURCE_KIND_PDF_PORTFOLIO,
)

# Datasets that hold extracted business records. QA Review and Source
# Documents are always derivable, so they never count as "found something".
_RECORD_DATASETS = (
    "all_fields",
    "clins",
    "funding",
    "performance_delivery",
    "attachments",
    "clauses",
    "far_references",
    "dfars",
)


def _is_needs_review(value: str | None) -> bool:
    return bool(value) and "review" in value.lower()


def _record_counts(doc: NormalizedV3Document) -> tuple[int, int]:
    total = 0
    needs_review = 0
    for name in _RECORD_DATASETS:
        rows = getattr(doc, name)
        total += len(rows)
        needs_review += sum(1 for row in rows if _is_needs_review(row.qa_status))
    if doc.contract_summary is not None:
        total += 1
        if _is_needs_review(doc.contract_summary.qa_status):
            needs_review += 1
    return total, needs_review


def build_extraction_outcome(
    doc: NormalizedV3Document, provenance: dict | None
) -> ExtractionOutcome:
    v3_record = (provenance or {}).get("v3_extraction") or None
    inspection = (v3_record or {}).get("source_inspection") or {}
    embedded_names = [
        str(item.get("name")) for item in inspection.get("embedded_files") or []
    ]
    record_count, needs_review_count = _record_counts(doc)

    if inspection.get("kind") == SOURCE_KIND_PDF_PORTFOLIO:
        return ExtractionOutcome(
            status="special_source",
            title="PDF Portfolio: embedded documents need extraction",
            message=(
                "This file is an Adobe PDF Portfolio. Its visible page is only a "
                "placeholder asking to open it in Acrobat; the actual documents "
                f"are {len(embedded_names)} embedded file(s). Extract the embedded "
                "files and upload them to process their content."
            ),
            details=embedded_names,
            record_count=record_count,
            needs_review_count=needs_review_count,
        )

    if v3_record is not None and v3_record.get("status") == "failed":
        error = v3_record.get("error")
        return ExtractionOutcome(
            status="failed",
            title="Staging extraction failed",
            message=(
                "The document was processed, but building the staging workbook "
                "failed. Re-run extraction; if it fails again, check Processing "
                "Details for the error."
            ),
            details=[f"Error type: {error}"] if error else [],
            record_count=record_count,
            needs_review_count=needs_review_count,
        )

    # Attachments on an ordinary PDF aren't a failure, but they may be the
    # only place the real content lives — say so alongside the results.
    embedded_note = (
        [f"Embedded file: {name}" for name in embedded_names]
        if inspection.get("kind") == SOURCE_KIND_PDF_EMBEDDED_FILES
        else []
    )

    if record_count > 0:
        if needs_review_count > 0:
            return ExtractionOutcome(
                status="needs_review",
                title="Extraction partially verified",
                message=(
                    f"{needs_review_count} of {record_count} record(s) need review "
                    "before export."
                ),
                details=embedded_note,
                record_count=record_count,
                needs_review_count=needs_review_count,
            )
        return ExtractionOutcome(
            status="populated",
            title="Extraction complete",
            message=f"{record_count} source-supported record(s) staged.",
            details=embedded_note,
            record_count=record_count,
            needs_review_count=0,
        )

    if v3_record is None:
        return ExtractionOutcome(
            status="pending",
            title="Staging results not available yet",
            message=(
                "No staging extraction has been recorded for this document. If "
                "extraction is still running, results will appear when it "
                "finishes; otherwise re-run extraction."
            ),
            record_count=0,
            needs_review_count=0,
        )

    return ExtractionOutcome(
        status="no_supported_fields",
        title="No supported business values identified",
        message=(
            "The document was processed, but no fields supported by the current "
            "staging profile were identified. Review Source Documents and QA "
            "Review for what was read."
        ),
        details=embedded_note,
        record_count=0,
        needs_review_count=0,
    )
