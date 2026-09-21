"use client";

import type { FieldRow } from "@/components/extraction/field-row";

interface FieldsDatasetTableProps {
  rows: FieldRow[];
  selectedId?: string | null;
  onSelectRow?: (row: FieldRow) => void;
}

/**
 * Primary business representation: field names as column headers,
 * one data row of clean extracted values. Evidence stays in detail views.
 */
export default function FieldsDatasetTable({
  rows,
  selectedId = null,
  onSelectRow,
}: FieldsDatasetTableProps) {
  const withValues = rows.filter(
    (row) => row.status !== "not_found" || row.value != null,
  );
  const columns = withValues.length > 0 ? withValues : rows.slice(0, 12);

  if (columns.length === 0) {
    return (
      <p className="rounded-xl border border-border bg-surface px-4 py-6 text-sm text-text-secondary">
        No fields extracted yet.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-soft">
            {columns.map((row) => (
              <th
                key={row.id}
                scope="col"
                className={[
                  "whitespace-nowrap px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary",
                  selectedId === row.id ? "bg-primary/10 text-primary" : "",
                ].join(" ")}
              >
                <button
                  type="button"
                  className="text-left hover:text-primary"
                  onClick={() => onSelectRow?.(row)}
                  title={row.label}
                >
                  {row.id || row.label}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {columns.map((row) => {
              const empty =
                row.value == null ||
                String(row.value).trim() === "" ||
                row.status === "empty" ||
                row.status === "not_found";
              const needsReview =
                empty ||
                row.status === "validation_failed" ||
                row.status === "low_confidence";
              return (
                <td
                  key={row.id}
                  className={[
                    "max-w-[14rem] border-t border-border px-3 py-2.5 align-top",
                    selectedId === row.id ? "bg-primary/5" : "",
                  ].join(" ")}
                >
                  <button
                    type="button"
                    className="w-full text-left"
                    onClick={() => onSelectRow?.(row)}
                  >
                    {needsReview && empty ? (
                      <span className="text-xs font-medium text-warning">
                        Needs Review
                      </span>
                    ) : (
                      <span className="block truncate font-medium text-foreground">
                        {String(row.value ?? "")}
                      </span>
                    )}
                  </button>
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
      <p className="border-t border-border px-3 py-2 text-xs text-text-muted">
        Business dataset view — one row for this document. Open a cell for
        source evidence, confidence, and review actions below.
      </p>
    </div>
  );
}
