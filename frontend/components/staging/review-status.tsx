"use client";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import type { ReviewStatus, StagingCell } from "@/lib/staging-workbook";

const TONE: Record<ReviewStatus, string> = {
  Verified: "bg-success/15 text-success",
  "Needs Review": "bg-warning/15 text-warning",
  Missing: "bg-surface-soft text-text-muted",
};

export function ReviewStatusBadge({ status }: { status: ReviewStatus | null }) {
  if (!status) return null;
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${TONE[status]}`}
    >
      {status}
    </span>
  );
}

export function formatCellValue(cell: StagingCell): string {
  const { value } = cell;
  if (value == null) return "";
  if (typeof value === "number" && cell.value_type === "money") {
    return value.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return String(value);
}

/** A cell can open source verification when its own provenance points at
 * a page of the document (system facts and non-paginated sources can't). */
export function canOpenSource(cell: StagingCell): boolean {
  const page = cell.provenance?.source_page;
  return cell.value != null && typeof page === "number" && page > 0;
}

/** Builds the source-verification request from ONE cell's provenance, so
 * the viewer highlights that cell rather than its whole record. */
export function cellSourceRequest(
  cell: StagingCell,
  requestId: string,
): SourceViewRequest | null {
  const provenance = cell.provenance;
  if (!provenance || !canOpenSource(cell)) return null;
  return {
    id: requestId,
    pageNumber: provenance.source_page as number,
    highlightText: provenance.highlight_text,
    anchorText: provenance.anchor_text,
    region: provenance.source_bbox,
    label: cell.display_label,
    value: formatCellValue(cell),
    evidenceText: provenance.evidence_text,
    extractionMethod: provenance.extraction_method,
    reviewStatus: cell.review_status,
    reviewReasons: cell.review_reasons,
    verified: cell.review_status === "Verified",
  };
}
