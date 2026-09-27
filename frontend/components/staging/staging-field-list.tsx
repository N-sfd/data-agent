"use client";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import {
  ReviewStatusBadge,
  cellSourceRequest,
  formatCellValue,
  locationLabel,
} from "@/components/staging/review-status";
import type { StagingDataset } from "@/lib/staging-workbook";

interface StagingFieldListProps {
  dataset: StagingDataset;
  onOpenSource?: (request: SourceViewRequest) => void;
  selectedId?: string | null;
}

/** A single-record dataset (Contract Summary, Document Summary, later
 * Invoice Summary) rendered as Field | Value | Page | Method | Status. */
export default function StagingFieldList({
  dataset,
  onOpenSource,
  selectedId,
}: StagingFieldListProps) {
  const record = dataset.records[0];
  if (!record) return null;

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[640px] divide-y divide-border text-sm">
        <thead className="bg-surface-soft">
          <tr>
            {["Field", "Value", "Location", "Method", "Status"].map((label) => (
              <th
                key={label}
                className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {dataset.columns.map((column) => {
            const cell = record.cells[column.canonical_field];
            if (!cell) return null;
            const requestId = `${dataset.dataset_id}:${record.record_id}:${column.canonical_field}`;
            const request = cellSourceRequest(cell, requestId);
            const text = formatCellValue(cell);
            return (
              <tr
                key={column.canonical_field}
                className={`align-top ${selectedId === requestId ? "bg-primary/[0.06]" : ""}`}
              >
                <td className="whitespace-nowrap px-3 py-2 text-text-secondary">
                  {column.display_label}
                </td>
                <td className="max-w-md px-3 py-2">
                  {cell.value == null ? (
                    <span className="text-text-muted">—</span>
                  ) : request && onOpenSource ? (
                    <button
                      type="button"
                      onClick={() => onOpenSource(request)}
                      className="text-left font-medium text-foreground underline decoration-dotted decoration-text-muted hover:text-primary hover:decoration-primary"
                      title="View source evidence"
                    >
                      {text}
                    </button>
                  ) : (
                    <span className="font-medium text-foreground">{text}</span>
                  )}
                  {cell.review_status === "Needs Review" && cell.review_reasons.length > 0 && (
                    <p className="mt-0.5 text-xs text-warning">{cell.review_reasons[0]}</p>
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-2 tabular-nums text-text-secondary">
                  {locationLabel(cell)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-xs text-text-secondary">
                  {cell.provenance?.extraction_method ?? "—"}
                </td>
                <td className="px-3 py-2">
                  <ReviewStatusBadge status={cell.review_status} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
