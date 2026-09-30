"use client";

import { useMemo, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import {
  ReviewStatusBadge,
  cellSourceRequest,
  formatCellValue,
  locationLabel,
} from "@/components/staging/review-status";
import StagingRecordDrawer from "@/components/staging/staging-record-drawer";
import type { StagingColumn, StagingDataset, StagingRecord } from "@/lib/staging-workbook";

type StatusFilter = "all" | "Verified" | "Needs Review" | "complete" | "partial";

interface StagingDatasetTableProps {
  dataset: StagingDataset;
  /** Needed to load full records of a compact dataset. */
  documentId?: string;
  onOpenSource?: (request: SourceViewRequest) => void;
  onOpenDataset?: (datasetId: string) => void;
  selectedId?: string | null;
  pageSize?: number;
  dense?: boolean;
}

const DEFAULT_PAGE_SIZE = 25;
const EXPAND_THRESHOLD = 80;

function recordEvidence(record: StagingRecord): { location: string; evidence: string } {
  for (const cell of Object.values(record.cells)) {
    if (cell.provenance?.evidence_text || cell.provenance?.source_page) {
      return { location: locationLabel(cell), evidence: cell.provenance.evidence_text ?? "" };
    }
  }
  return { location: "—", evidence: "" };
}

function resultTone(value: string): string {
  const upper = value.toUpperCase();
  if (upper.startsWith("PASS")) return "font-medium text-success";
  if (upper.startsWith("REVIEW") || upper.startsWith("NOT FOUND")) return "font-medium text-warning";
  return "text-foreground";
}

/** Any repeating dataset of any profile. Every populated cell opens source
 * verification with that cell's own provenance. */
function gridColumns(dataset: StagingDataset): StagingColumn[] {
  const grid = dataset.grid_fields ?? [];
  if (grid.length === 0) return dataset.columns;
  return grid
    .map((field) => dataset.columns.find((column) => column.canonical_field === field))
    .filter((column): column is StagingColumn => Boolean(column));
}

export default function StagingDatasetTable({
  dataset,
  documentId,
  onOpenSource,
  onOpenDataset,
  selectedId,
  pageSize = DEFAULT_PAGE_SIZE,
  dense = false,
}: StagingDatasetTableProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [openRecord, setOpenRecord] = useState<StagingRecord | null>(null);

  const columns = gridColumns(dataset);
  // A compact grid shows only its declared columns; every other field,
  // with its evidence, is in the record detail drawer.
  const hasDetails = (dataset.grid_fields?.length ?? 0) > 0 && (!dataset.compact || Boolean(documentId));
  const isBusiness = dataset.role === "business";
  const showEvidence = isBusiness && !hasDetails && !dense;
  const hasStatus = isBusiness && dataset.records.some((r) => r.record_status != null);
  const hasLinks = dataset.records.some((r) => r.links_to_dataset);

  const isClin = dataset.dataset_id === "clins";

  function clinShape(record: StagingRecord): "complete" | "partial" {
    const value = (field: string) => record.cells[field]?.value;
    const described = Boolean(value("contract.clin.description"));
    const priced = Boolean(
      value("contract.clin.max_amount") ||
        value("contract.clin.unit_price") ||
        value("contract.clin.max_quantity") ||
        value("contract.clin.unit"),
    );
    return described && priced ? "complete" : "partial";
  }

  const filtered = useMemo(() => {
    if (statusFilter === "all") return dataset.records;
    if (statusFilter === "complete" || statusFilter === "partial") {
      return dataset.records.filter((record) => clinShape(record) === statusFilter);
    }
    return dataset.records.filter((record) => record.record_status === statusFilter);
  }, [dataset.records, statusFilter]);

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
      {isClin && (
        <p className="text-xs text-text-secondary">
          {dataset.records.filter((record) => clinShape(record) === "complete").length} complete ·{" "}
          {dataset.records.filter((record) => clinShape(record) === "partial").length} partial. Partial rows
          only have a CLIN identifier in the source; missing description, quantity, unit, or amount is not filled in.
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {hasStatus || isClin ? (
          <div className="flex flex-wrap gap-1 rounded-lg border border-border bg-surface-soft p-0.5 text-xs">
            {(isClin
              ? (["all", "complete", "partial", "Needs Review"] as StatusFilter[])
              : (["all", "Verified", "Needs Review"] as StatusFilter[])
            ).map((value) => (
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
                {value === "all" ? "All" : value === "complete" ? "Complete" : value === "partial" ? "Partial" : value}
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
            <table className={`w-full min-w-max divide-y divide-border text-sm ${dense ? "[&_td]:py-1.5 [&_th]:py-1.5" : ""}`}>
              <thead className="sticky top-0 z-10 bg-surface-soft">
                <tr>
                  {columns.map((column, columnIndex) => (
                    <th
                      key={column.canonical_field}
                      className={[
                        "whitespace-nowrap px-3 text-left text-[11px] font-medium text-text-muted",
                        dense ? "py-2" : "min-w-[110px] py-2 text-xs font-semibold uppercase tracking-wide text-text-secondary",
                        dense && columnIndex === 0 ? "sticky left-0 z-20 bg-surface-soft" : "",
                      ].join(" ")}
                    >
                      {column.display_label}
                    </th>
                  ))}
                  {showEvidence && (
                    <>
                      <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                        Location
                      </th>
                      <th className="min-w-[220px] whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                        Evidence
                      </th>
                    </>
                  )}
                  {isBusiness && (
                    <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                      Status
                    </th>
                  )}
                  {hasDetails && <th className="px-3 py-2" />}
                  {hasLinks && <th className="px-3 py-2" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paged.map((record) => {
                  const { location, evidence } = recordEvidence(record);
                  const isExpanded = expanded.has(record.record_id);
                  return (
                    <tr key={record.record_id} className="align-top hover:bg-surface-soft/60">
                      {columns.map((column, columnIndex) => {
                        const cell = record.cells[column.canonical_field];
                        const requestId = `${dataset.dataset_id}:${record.record_id}:${column.canonical_field}`;
                        const request = cell ? cellSourceRequest(cell, requestId) : null;
                        const text = cell ? formatCellValue(cell) : "";
                        const selected = selectedId === requestId;
                        return (
                          <td
                            key={column.canonical_field}
                            className={[
                              "max-w-xs px-3",
                              dense ? "h-11 max-w-[16rem] py-0 align-middle" : "py-2 align-top",
                              selected ? "bg-primary/[0.08]" : "",
                              dense && columnIndex === 0 ? "sticky left-0 bg-surface" : "",
                            ].join(" ")}
                            title={text}
                          >
                            {!text ? (
                              <span className="text-text-muted">—</span>
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
                      {showEvidence && (
                        <>
                          <td className="whitespace-nowrap px-3 py-2 tabular-nums text-text-secondary">
                            {location}
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
                        </>
                      )}
                      {isBusiness && (
                        <td className="whitespace-nowrap px-3 py-2">
                          <ReviewStatusBadge status={record.record_status} />
                        </td>
                      )}
                      {hasDetails && (
                        <td className="whitespace-nowrap px-3 py-2 text-right">
                          <button
                            type="button"
                            onClick={() => setOpenRecord(record)}
                            className="text-xs font-medium text-primary hover:underline"
                          >
                            Details
                          </button>
                        </td>
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

          {openRecord && hasDetails && (
            <StagingRecordDrawer
              documentId={documentId ?? ""}
              dataset={dataset}
              record={openRecord}
              onClose={() => setOpenRecord(null)}
              onOpenSource={onOpenSource}
            />
          )}

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
