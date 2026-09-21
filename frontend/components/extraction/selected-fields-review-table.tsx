"use client";

import type { FieldRow } from "@/components/extraction/field-row";
import type { SourceViewRequest } from "@/components/source-verification-panel";

interface SelectedFieldsReviewTableProps {
  rows: FieldRow[];
  selectedId?: string | null;
  onViewSource?: (request: SourceViewRequest) => void;
  onSelectRow?: (row: FieldRow) => void;
}

function statusLabel(row: FieldRow): string {
  if (row.correction?.action === "reject") return "Rejected";
  if (row.correction?.action === "verify" || row.verified) return "Verified";
  if (row.correction?.action === "edit") return "Edited";
  if (row.status === "not_found" || row.status === "empty") return "Needs Review";
  if (row.status === "validation_failed" || row.status === "low_confidence") {
    return "Needs Review";
  }
  return "Extracted";
}

function statusClass(row: FieldRow): string {
  const label = statusLabel(row);
  if (label === "Verified") return "text-success";
  if (label === "Rejected") return "text-danger";
  if (label === "Needs Review") return "text-warning";
  if (label === "Edited") return "text-primary";
  return "text-text-secondary";
}

/**
 * Interactive review layout: one row per selected scalar field.
 * Business CSV/XLSX remain wide (fields as columns) via export paths.
 */
export default function SelectedFieldsReviewTable({
  rows,
  selectedId = null,
  onViewSource,
  onSelectRow,
}: SelectedFieldsReviewTableProps) {
  if (rows.length === 0) {
    return (
      <p className="rounded-xl border border-border bg-surface px-4 py-6 text-sm text-text-secondary">
        No selected fields to display.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-soft">
            <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Selected Field
            </th>
            <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Extracted Value
            </th>
            <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Page
            </th>
            <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Confidence
            </th>
            <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const page =
              row.evidence?.page_number ?? row.scalar?.page ?? null;
            const empty =
              row.value == null ||
              String(row.value).trim() === "" ||
              row.status === "empty" ||
              row.status === "not_found";
            const selected = selectedId === row.id;
            return (
              <tr
                key={row.id}
                id={`field-row-${row.id}`}
                className={[
                  "border-t border-border",
                  selected ? "bg-primary/5" : "hover:bg-surface-soft/80",
                ].join(" ")}
              >
                <td className="max-w-[14rem] px-3 py-2.5 align-top">
                  <button
                    type="button"
                    className="text-left font-medium text-foreground hover:text-primary"
                    onClick={() => onSelectRow?.(row)}
                  >
                    {row.label}
                  </button>
                </td>
                <td className="max-w-[20rem] px-3 py-2.5 align-top">
                  <button
                    type="button"
                    className="w-full text-left"
                    onClick={() => {
                      onSelectRow?.(row);
                      if (onViewSource && page) {
                        onViewSource({
                          id: row.id,
                          pageNumber: page,
                          highlightText:
                            row.evidence?.source_text ||
                            String(row.value ?? ""),
                          label: row.label,
                          value: String(row.value ?? ""),
                          confidence: row.confidence ?? undefined,
                          verified: row.verified,
                        });
                      }
                    }}
                  >
                    {empty ? (
                      <span className="text-xs font-medium text-warning">
                        Needs Review
                      </span>
                    ) : (
                      <span className="block truncate font-medium text-foreground">
                        {String(row.value)}
                      </span>
                    )}
                  </button>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 align-top text-text-secondary">
                  {page ?? "—"}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 align-top text-text-secondary">
                  {row.confidence != null
                    ? `${row.confidence_band ?? ""} ${row.confidence.toFixed(2)}`.trim()
                    : "—"}
                </td>
                <td
                  className={[
                    "whitespace-nowrap px-3 py-2.5 align-top text-xs font-semibold",
                    statusClass(row),
                  ].join(" ")}
                >
                  {statusLabel(row)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="border-t border-border px-3 py-2 text-xs text-text-muted">
        Review table — one row per selected field. Click a value to jump to
        source evidence. CSV/Excel exports use the wide business layout
        (field names as columns).
      </p>
    </div>
  );
}
