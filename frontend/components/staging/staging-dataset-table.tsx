"use client";

import { useMemo, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import {
  ReviewStatusBadge,
  cellSourceRequest,
  formatCellValue,
} from "@/components/staging/review-status";
import type { StagingDataset, StagingRecord } from "@/lib/staging-workbook";

type StatusFilter = "all" | "Verified" | "Needs Review";

interface StagingDatasetTableProps {
  dataset: StagingDataset;
  onOpenSource?: (request: SourceViewRequest) => void;
  onOpenDataset?: (datasetId: string) => void;
  selectedId?: string | null;
  pageSize?: number;
}

const DEFAULT_PAGE_SIZE = 25;
const EXPAND_THRESHOLD = 80;

function recordEvidence(record: StagingRecord): { page: number | null; evidence: string } {
  for (const cell of Object.values(record.cells)) {
    if (cell.provenance?.evidence_text || cell.provenance?.source_page) {
      return {
        page: cell.provenance.source_page,
        evidence: cell.provenance.evidence_text ?? "",
      };
    }
  }
  return { page: null, evidence: "" };
}

function resultTone(value: string): string {
  const upper = value.toUpperCase();
  if (upper.startsWith("PASS")) return "font-medium text-success";
  if (upper.startsWith("REVIEW") || upper.startsWith("NOT FOUND")) return "font-medium text-warning";
  return "text-foreground";
}

/** Any repeating dataset of any profile. Every populated cell opens source
 * verification with that cell's own provenance. */
export default function StagingDatasetTable({
  dataset,
  onOpenSource,
  onOpenDataset,
  selectedId,
  pageSize = DEFAULT_PAGE_SIZE,
}: StagingDatasetTableProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const isBusiness = dataset.role === "business";
  const hasStatus = isBusiness && dataset.records.some((r) => r.record_status != null);
  const hasLinks = dataset.records.some((r) => r.links_to_dataset);

  const filtered = useMemo(
    () =>
      statusFilter === "all"
        ? dataset.records
        : dataset.records.filter((r) => r.record_status === statusFilter),
    [dataset.records, statusFilter],
  );

  // Reset to the first page when the filter or dataset changes (render-time
  // state adjustment, as in React's docs, instead of an extra effect pass).
  const [resetKey, setResetKey] = useState({ statusFilter, records: dataset.records });
  if (resetKey.statusFilter !== statusFilter || resetKey.records !== dataset.records) {
    setResetKey({ statusFilter, records: dataset.records });
    if (page !== 0) setPage(0);
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const clampedPage = Math.min(page, totalPages - 1);
  const paged = filtered.slice(clampedPage * pageSize, clampedPage * pageSize + pageSize);

  if (dataset.records.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface-soft px-4 py-10 text-center text-sm text-text-secondary">
        No source-supported records found.
      </div>
    );
  }

  function toggleExpanded(recordId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(recordId)) next.delete(recordId);
      else next.add(recordId);
      return next;
    });
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {hasStatus ? (
          <div className="flex gap-1 rounded-lg border border-border bg-surface-soft p-0.5 text-xs">
            {(["all", "Verified", "Needs Review"] as StatusFilter[]).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setStatusFilter(value)}
                className={[
                  "rounded-md px-2.5 py-1 font-medium transition",
                  statusFilter === value
                    ? "bg-surface text-foreground shadow-sm"
                    : "text-text-secondary hover:text-foreground",
                ].join(" ")}
              >
                {value === "all" ? "All" : value}
              </button>
            ))}
          </div>
        ) : (
          <span />
        )}
        <span className="text-xs text-text-secondary">
          {filtered.length} of {dataset.records.length} record
          {dataset.records.length === 1 ? "" : "s"}
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-soft px-4 py-10 text-center text-sm text-text-secondary">
          No records match this filter.
        </div>
      ) : (
        <>
          <div className="max-h-[65vh] overflow-auto rounded-xl border border-border">
            <table className="w-full min-w-max divide-y divide-border text-sm">
              <thead className="sticky top-0 z-10 bg-surface-soft">
                <tr>
                  {dataset.columns.map((column) => (
                    <th
                      key={column.canonical_field}
                      className="min-w-[110px] whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary"
                    >
                      {column.display_label}
                    </th>
                  ))}
                  {isBusiness && (
                    <>
                      <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                        Page
                      </th>
                      <th className="min-w-[220px] whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                        Evidence
                      </th>
                      <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                        Status
                      </th>
                    </>
                  )}
                  {hasLinks && <th className="px-3 py-2" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paged.map((record) => {
                  const { page: sourcePage, evidence } = recordEvidence(record);
                  const isExpanded = expanded.has(record.record_id);
                  return (
                    <tr key={record.record_id} className="align-top hover:bg-surface-soft/60">
                      {dataset.columns.map((column) => {
                        const cell = record.cells[column.canonical_field];
                        const requestId = `${dataset.dataset_id}:${record.record_id}:${column.canonical_field}`;
                        const request = cell ? cellSourceRequest(cell, requestId) : null;
                        const text = cell ? formatCellValue(cell) : "";
                        const selected = selectedId === requestId;
                        return (
                          <td
                            key={column.canonical_field}
                            className={`max-w-xs px-3 py-2 ${selected ? "bg-primary/[0.08]" : ""}`}
                            title={text}
                          >
                            {!text ? (
                              cell?.review_status === "Missing" ? (
                                <ReviewStatusBadge status="Missing" />
                              ) : (
                                <span className="text-text-muted">—</span>
                              )
                            ) : request && onOpenSource ? (
                              <button
                                type="button"
                                onClick={() => onOpenSource(request)}
                                className="block max-w-xs truncate text-left text-foreground underline decoration-dotted decoration-text-muted hover:text-primary hover:decoration-primary"
                              >
                                {text}
                              </button>
                            ) : column.canonical_field === "qa.result" ? (
                              <span className={resultTone(text)}>{text}</span>
                            ) : (
                              <span className="block max-w-xs truncate text-foreground">{text}</span>
                            )}
                          </td>
                        );
                      })}
                      {isBusiness && (
                        <>
                          <td className="whitespace-nowrap px-3 py-2 tabular-nums text-text-secondary">
                            {sourcePage ?? "—"}
                          </td>
                          <td className="px-3 py-2 text-text-secondary">
                            <div
                              className={isExpanded ? "max-w-md whitespace-pre-wrap" : "max-w-md truncate"}
                              title={isExpanded ? undefined : evidence}
                            >
                              {evidence || <span className="text-text-muted">—</span>}
                            </div>
                            {evidence.length > EXPAND_THRESHOLD && (
                              <button
                                type="button"
                                onClick={() => toggleExpanded(record.record_id)}
                                className="mt-0.5 text-xs font-medium text-primary hover:underline"
                              >
                                {isExpanded ? "Show less" : "Show more"}
                              </button>
                            )}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2">
                            <ReviewStatusBadge status={record.record_status} />
                          </td>
                        </>
                      )}
                      {hasLinks && (
                        <td className="whitespace-nowrap px-3 py-2 text-right">
                          {record.links_to_dataset && onOpenDataset && (
                            <button
                              type="button"
                              onClick={() => onOpenDataset(record.links_to_dataset as string)}
                              className="text-xs font-medium text-primary hover:underline"
                            >
                              View dataset →
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between text-xs text-text-secondary">
              <button
                type="button"
                disabled={clampedPage === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="rounded-md border border-border px-2.5 py-1 font-medium disabled:opacity-40"
              >
                Previous
              </button>
              <span>
                Page {clampedPage + 1} of {totalPages}
              </span>
              <button
                type="button"
                disabled={clampedPage >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                className="rounded-md border border-border px-2.5 py-1 font-medium disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
