"""Portfolio-wide aggregates for the Analytics, Insights and Risk pages.

Read-only and computed with grouped queries over what extraction already
stored (documents, staging resolutions, review fields, contract summaries,
performance periods, clause references). Always scoped to the caller's
visible documents.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone

from dateutil import parser as date_parser
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_clause_reference import DocumentClauseReference
from app.models.document_contract_summary import DocumentContractSummary
from app.models.document_metadata_field import DocumentMetadataField
from app.models.document_page import DocumentPage
from app.models.document_performance_period import DocumentPerformancePeriod
from app.models.document_staging_workbook import DocumentStagingWorkbook

LOW_CONFIDENCE = 0.8
TOP_N = 8
RISK_LIMIT = 200
EXPIRING_WINDOW_DAYS = 180
RECENTLY_ENDED_DAYS = 30
COMPLETED = {"completed", "completed_with_warnings"}


def _parse_date(value: str | None) -> date | None:
    if not value or not value.strip():
        return None
    try:
        parsed = date_parser.parse(value.strip(), fuzzy=False, default=datetime(1900, 1, 1))
    except (ValueError, OverflowError, TypeError):
        return None
    return parsed.date() if parsed.year > 1900 else None


def _top(counter: Counter, limit: int = TOP_N) -> list[dict]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def build_portfolio(database: Session, visible_ids, today: date | None = None) -> dict:
    """`visible_ids` is a selectable of the caller's document ids."""

    today = today or datetime.now(timezone.utc).date()
    documents = list(
        database.execute(
            select(
                Document.id,
                Document.original_filename,
                Document.document_type,
                Document.processing_status,
                Document.page_count,
                Document.processing_duration_seconds,
                Document.uploaded_at,
                Document.checksum_sha256,
            ).where(Document.id.in_(visible_ids))
        )
    )
    names = {row.id: row.original_filename for row in documents}

    # --- document mix: staging family first, then AI classification -------
    families = {
        row.document_id: (row.document_family, row.document_family_label)
        for row in database.execute(
            select(
                DocumentStagingWorkbook.document_id,
                DocumentStagingWorkbook.document_family,
                DocumentStagingWorkbook.document_family_label,
            ).where(DocumentStagingWorkbook.document_id.in_(visible_ids))
        )
    }
    mix: Counter = Counter()
    for row in documents:
        family = families.get(row.id)
        if family and family[0] not in ("unknown", "generic_business"):
            mix[family[1] or family[0]] += 1
        elif row.document_type:
            mix[row.document_type] += 1
        else:
            mix["Unclassified"] += 1

    # --- volume and processing -------------------------------------------
    by_month: Counter = Counter(row.uploaded_at.strftime("%Y-%m") for row in documents if row.uploaded_at)
    months = sorted(by_month)[-12:]
    durations = [row.processing_duration_seconds for row in documents if row.processing_duration_seconds]
    status_counts = Counter(
        "processed" if row.processing_status in COMPLETED
        else "failed" if row.processing_status == "failed"
        else "not_processed" if row.processing_status in (None, "not_processed")
        else "processing"
        for row in documents
    )
    ocr_pages = database.scalar(
        select(func.count()).select_from(DocumentPage).where(
            DocumentPage.document_id.in_(visible_ids), DocumentPage.ocr_attempted.is_(True)
        )
    ) or 0

    # --- review ---------------------------------------------------------------
    review_rows = list(
        database.execute(
            select(
                DocumentMetadataField.review_status,
                func.count(),
                func.avg(DocumentMetadataField.confidence),
            )
            .where(DocumentMetadataField.document_id.in_(visible_ids))
            .group_by(DocumentMetadataField.review_status)
        )
    )
    review_counts = {status: count for status, count, _ in review_rows}
    field_total = sum(review_counts.values())
    weighted = sum((avg or 0) * count for _, count, avg in review_rows)
    low_confidence_pending = dict(
        database.execute(
            select(DocumentMetadataField.document_id, func.count())
            .where(
                DocumentMetadataField.document_id.in_(visible_ids),
                DocumentMetadataField.review_status == "pending",
                DocumentMetadataField.confidence < LOW_CONFIDENCE,
            )
            .group_by(DocumentMetadataField.document_id)
        ).all()
    )

    # --- contracts ------------------------------------------------------------
    summaries = list(
        database.scalars(select(DocumentContractSummary).where(DocumentContractSummary.document_id.in_(visible_ids)))
    )
    agencies, contractors, vehicles, naics = Counter(), Counter(), Counter(), Counter()
    for summary in summaries:
        for counter, value in (
            (agencies, summary.agency_office),
            (contractors, summary.contractor),
            (vehicles, summary.contract_vehicle),
            (naics, summary.naics),
        ):
            if value and value.strip():
                counter[value.strip()[:80]] += 1

    clause_rows = list(
        database.execute(
            select(
                DocumentClauseReference.clause_number,
                func.min(DocumentClauseReference.title),
                func.count(func.distinct(DocumentClauseReference.document_id)),
            )
            .where(DocumentClauseReference.document_id.in_(visible_ids))
            .group_by(DocumentClauseReference.clause_number)
            .order_by(func.count(func.distinct(DocumentClauseReference.document_id)).desc())
            .limit(12)
        )
    )
    clause_total = database.scalar(
        select(func.count()).select_from(DocumentClauseReference).where(
            DocumentClauseReference.document_id.in_(visible_ids)
        )
    ) or 0

    contract_numbers = {summary.document_id: summary.contract_number for summary in summaries}
    expiring: list[dict] = []
    for period in database.scalars(
        select(DocumentPerformancePeriod).where(DocumentPerformancePeriod.document_id.in_(visible_ids))
    ):
        end = _parse_date(period.end_date)
        if end is None:
            continue
        days_left = (end - today).days
        if -RECENTLY_ENDED_DAYS <= days_left <= EXPIRING_WINDOW_DAYS:
            expiring.append({
                "document_id": period.document_id,
                "filename": names.get(period.document_id, ""),
                "contract_number": contract_numbers.get(period.document_id),
                "period": period.period_label,
                "end_date": end.isoformat(),
                "days_left": days_left,
            })
    expiring.sort(key=lambda item: item["days_left"])

    # --- risk register ----------------------------------------------------------
    risks: list[dict] = []

    def risk(document_id: str, kind: str, severity: str, detail: str) -> None:
        risks.append({
            "document_id": document_id,
            "filename": names.get(document_id, ""),
            "kind": kind,
            "severity": severity,
            "detail": detail,
        })

    for row in documents:
        if row.processing_status == "failed":
            risk(row.id, "Processing failed", "high", "Extraction did not complete; the document has no staged data.")
    for item in expiring:
        if item["days_left"] < 0:
            risk(item["document_id"], "Period ended", "medium", f"{item['period']} ended {item['end_date']}.")
        elif item["days_left"] <= 90:
            risk(item["document_id"], "Period ending soon", "high", f"{item['period']} ends {item['end_date']} ({item['days_left']} days).")
    for document_id, count in low_confidence_pending.items():
        risk(document_id, "Low-confidence values", "medium", f"{count} unreviewed value{'s' if count != 1 else ''} below {int(LOW_CONFIDENCE * 100)}% confidence.")
    for summary in summaries:
        if not (summary.contract_number or "").strip():
            risk(summary.document_id, "Missing contract number", "medium", "A contract was staged without a contract number.")
    checksums: dict[str, list[str]] = defaultdict(list)
    for row in documents:
        if row.checksum_sha256:
            checksums[row.checksum_sha256].append(row.id)
    duplicate_groups = [ids for ids in checksums.values() if len(ids) > 1]
    for ids in duplicate_groups:
        risk(ids[0], "Duplicate uploads", "low", f"The same file was uploaded {len(ids)} times.")
    for row in documents:
        if row.processing_status in COMPLETED and not row.document_type and row.id not in families:
            risk(row.id, "Unclassified", "low", "Processed, but no document type or staging profile was resolved.")

    order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda item: (order[item["severity"]], item["kind"], item["filename"]))
    by_kind = Counter(item["kind"] for item in risks)
    by_severity = Counter(item["severity"] for item in risks)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "documents": len(documents),
            "pages": sum(row.page_count or 0 for row in documents),
            "ocr_pages": ocr_pages,
            "processed": status_counts["processed"],
            "processing": status_counts["processing"],
            "not_processed": status_counts["not_processed"],
            "failed": status_counts["failed"],
            "average_processing_seconds": sum(durations) / len(durations) if durations else None,
            "staged": len(families),
        },
        "document_mix": _top(mix, 12),
        "uploads_by_month": [{"month": month, "count": by_month[month]} for month in months],
        "review": {
            "fields": field_total,
            "pending": review_counts.get("pending", 0),
            "accepted": review_counts.get("accepted", 0) + review_counts.get("approved", 0),
            "edited": review_counts.get("edited", 0),
            "rejected": review_counts.get("rejected", 0),
            "average_confidence": weighted / field_total if field_total else None,
            "low_confidence_documents": len(low_confidence_pending),
        },
        "contracts": {
            "count": len(summaries),
            "agencies": _top(agencies),
            "contractors": _top(contractors),
            "vehicles": _top(vehicles),
            "naics": _top(naics),
        },
        "clauses": {
            "references": clause_total,
            "top": [
                {"clause_number": number, "title": title or "", "documents": count}
                for number, title, count in clause_rows
            ],
        },
        "expiring": expiring[:50],
        "risks": {
            "total": len(risks),
            "by_severity": {key: by_severity.get(key, 0) for key in ("high", "medium", "low")},
            "by_kind": _top(by_kind, 12),
            "items": risks[:RISK_LIMIT],
        },
    }
