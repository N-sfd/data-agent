"use client";

import { useMemo, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import QaBadge, { isNeedsReview } from "@/components/extraction/v3-qa-badge";

type StatusFilter = "all" | "verified" | "needs_review";

interface V3DatasetTableProps {
  /** Used to build a stable row id for source-verification requests. */
  datasetId: string;
  columns: [string, string][];
  rows: Record<string, unknown>[];
  /** null when this dataset has no per-row QA status (Source Documents). */
  qaStatusKey?: string | null;
  sourcePageKey?: string;
  evidenceKey?: string;
  /** [labelKey, valueKey] used to label the source-verification popover. */
  identityColumns?: [string, string];
  onOpenSource?: (request: SourceViewRequest) => void;
  pageSize?: number;
}

const DEFAULT_PAGE_SIZE = 25;
const EXPAND_THRESHOLD = 80;

const WIDE_COLUMN_KEYS = new Set([
  "evidence",
  "description",
  "title_description",
  "requirement",
  "clause_title",
  "details",
  "subject_context",
  "action",
]);

export default function V3DatasetTable({
  datasetId,
  columns,
  rows,
  qaStatusKey = "qa_status",
  sourcePageKey = "source_page",
  evidenceKey = "evidence",
  identityColumns,
  onOpenSource,
  pageSize = DEFAULT_PAGE_SIZE,
}: V3DatasetTableProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const hasQaStatus =
    qaStatusKey != null && rows.some((row) => row[qaStatusKey] != null);

  const indexed = useMemo(
    () => rows.map((row, originalIndex) => ({ row, originalIndex })),
    [rows],
  );

  const filtered = useMemo(() => {
    if (!hasQaStatus || statusFilter === "all") return indexed;
    return indexed.filter(({ row }) => {
      const needsReview = qaStatusKey ? isNeedsReview(row[qaStatusKey]) : false;
      return statusFilter === "needs_review" ? needsReview : !needsReview;
    });
  }, [indexed, statusFilter, hasQaStatus, qaStatusKey]);

  // Reset to page 1 whenever the filter/dataset changes — done during
  // render (React's documented pattern for resetting state in response to
  // a prop/derived-value change) rather than in a useEffect, so it doesn't
  // cost an extra render pass.
  const [resetKeyRef, setResetKeyRef] = useState({ statusFilter, rows });
  if (resetKeyRef.statusFilter !== statusFilter || resetKeyRef.rows !== rows) {
    setResetKeyRef({ statusFilter, rows });
    if (page !== 0) setPage(0);
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const clampedPage = Math.min(page, totalPages - 1);
  const paged = filtered.slice(
    clampedPage * pageSize,
    clampedPage * pageSize + pageSize,
  );

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface-soft px-4 py-10 text-center text-sm text-text-secondary">
        No source-supported records found.
      </div>
    );
  }

  const [labelKey, valueKey] = identityColumns ?? [
    columns[0]?.[0] ?? "",
    columns[1]?.[0] ?? columns[0]?.[0] ?? "",
  ];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {hasQaStatus ? (
          <div className="flex gap-1 rounded-lg border border-border bg-surface-soft p-0.5 text-xs">
            {(["all", "verified", "needs_review"] as StatusFilter[]).map(
              (value) => (
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
                  {value === "all"
                    ? "All"
                    : value === "verified"
                      ? "Verified"
                      : "Needs Review"}
                </button>
              ),
            )}
          </div>
        ) : (
          <span />
        )}
        <span className="text-xs text-text-secondary">
          {filtered.length} of {rows.length} record{rows.length === 1 ? "" : "s"}
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
                  {columns.map(([key, label]) => (
                    <th
                      key={key}
                      className={[
                        "whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary",
                        WIDE_COLUMN_KEYS.has(key) ? "min-w-[220px]" : "min-w-[110px]",
                      ].join(" ")}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paged.map(({ row, originalIndex }) => {
                  const sourcePage = row[sourcePageKey];
                  const canOpenSource =
                    Boolean(onOpenSource) &&
                    typeof sourcePage === "number" &&
                    sourcePage > 0;
                  const isExpanded = expanded.has(originalIndex);

                  return (
                    <tr
                      key={originalIndex}
                      onClick={
                        canOpenSource
                          ? () => {
                              const evidence = row[evidenceKey];
                              onOpenSource?.({
                                id: `${datasetId}-${originalIndex}`,
                                pageNumber: sourcePage as number,
                                highlightText:
                                  typeof evidence === "string" ? evidence : null,
                                label:
                                  row[labelKey] != null
                                    ? String(row[labelKey])
                                    : undefined,
                                value:
                                  row[valueKey] != null
                                    ? String(row[valueKey])
                                    : undefined,
                              });
                            }
                          : undefined
                      }
                      className={
                        canOpenSource
                          ? "cursor-pointer hover:bg-surface-soft/60"
                          : "hover:bg-surface-soft/60"
                      }
                    >
                      {columns.map(([key]) => {
                        const value = row[key];

                        if (qaStatusKey && key === qaStatusKey) {
                          return (
                            <td key={key} className="whitespace-nowrap px-3 py-2">
                              <QaBadge value={value} />
                            </td>
                          );
                        }

                        if (key === evidenceKey) {
                          const text = value == null ? "" : String(value);
                          return (
                            <td key={key} className="px-3 py-2 text-foreground">
                              <div
                                className={
                                  isExpanded
                                    ? "max-w-md whitespace-pre-wrap"
                                    : "max-w-md truncate"
                                }
                                title={isExpanded ? undefined : text}
                              >
                                {text || <span className="text-text-muted">—</span>}
                              </div>
                              {text.length > EXPAND_THRESHOLD && (
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setExpanded((prev) => {
                                      const next = new Set(prev);
                                      if (next.has(originalIndex)) {
                                        next.delete(originalIndex);
                                      } else {
                                        next.add(originalIndex);
                                      }
                                      return next;
                                    });
                                  }}
                                  className="mt-0.5 text-xs font-medium text-primary hover:underline"
                                >
                                  {isExpanded ? "Show less" : "Show more"}
                                </button>
                              )}
                            </td>
                          );
                        }

                        return (
                          <td
                            key={key}
                            className="max-w-xs truncate whitespace-nowrap px-3 py-2 text-foreground"
                            title={value == null ? "" : String(value)}
                          >
                            {value == null ? (
                              <span className="text-text-muted">—</span>
                            ) : (
                              String(value)
                            )}
                          </td>
                        );
                      })}
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
