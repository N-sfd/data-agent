"use client";

import { Check, Eye, History, Pencil, X } from "lucide-react";
import { useState } from "react";

import {
  FIELD_ROW_STATUS_LABEL,
  type FieldRow,
} from "@/components/extraction/field-row";
import type { SourceViewRequest } from "@/components/source-verification-panel";

interface FieldsTableProps {
  title: string;
  rows: FieldRow[];
  onViewSource?: (request: SourceViewRequest) => void;
  onSaveCorrection?: (row: FieldRow, correctedValue: string) => Promise<void> | void;
}

function methodLabel(method: string | null): string {
  switch (method) {
    case "form_field":
      return "PDF Form Field";
    case "label_value":
      return "Label / Value";
    case "regex":
      return "Pattern Match";
    case "table":
      return "Table";
    case "ai":
      return "AI Fallback";
    case null:
      return "—";
    default:
      return method;
  }
}

const CONFIDENCE_BAND_STYLES: Record<string, string> = {
  high: "bg-success/10 text-success",
  medium: "bg-warning/10 text-warning",
  low: "bg-danger/10 text-danger",
};

function ConfidenceCell({ row }: { row: FieldRow }) {
  if (row.confidence == null || row.confidence_band == null) {
    return <span className="text-xs text-text-muted">—</span>;
  }
  const style = CONFIDENCE_BAND_STYLES[row.confidence_band] ?? CONFIDENCE_BAND_STYLES.medium;
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${style}`}
    >
      {row.confidence_band} · {Math.round(row.confidence * 100)}%
    </span>
  );
}

const STATUS_STYLES: Record<FieldRow["status"], string> = {
  extracted: "bg-success/10 text-success",
  empty: "bg-surface-soft text-text-secondary",
  low_confidence: "bg-warning/10 text-warning",
  validation_failed: "bg-danger/10 text-danger",
  not_found: "bg-surface-soft text-text-muted",
};

function StatusBadge({ status }: { status: FieldRow["status"] }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_STYLES[status]}`}
    >
      {FIELD_ROW_STATUS_LABEL[status]}
    </span>
  );
}

function displayValue(row: FieldRow): string {
  const current = row.correction ? row.correction.corrected_value : row.value;
  if (row.status === "not_found") return "";
  if (current === null || current === undefined || current === "") return "";
  return String(current);
}

function FieldTableRow({
  row,
  onViewSource,
  onSaveCorrection,
}: {
  row: FieldRow;
  onViewSource?: (request: SourceViewRequest) => void;
  onSaveCorrection?: (row: FieldRow, correctedValue: string) => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(displayValue(row));
  const [saving, setSaving] = useState(false);
  const value = displayValue(row);
  const canEdit = Boolean(onSaveCorrection) && row.status !== "not_found";

  async function handleSave() {
    if (!onSaveCorrection) return;
    setSaving(true);
    try {
      await onSaveCorrection(row, draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr
      id={`field-row-${row.id}`}
      className="scroll-mt-32 border-b border-border last:border-0 hover:bg-surface-soft"
    >
      <td className="px-3 py-2.5 align-top text-xs font-semibold uppercase tracking-wide text-text-muted sm:px-4">
        {row.label}
      </td>
      <td className="px-3 py-2.5 align-top text-sm font-medium text-foreground sm:px-4">
        {editing ? (
          <input
            autoFocus
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            className="w-full min-w-[10rem] rounded-lg border border-primary/40 bg-surface px-2 py-1 text-sm outline-none"
          />
        ) : value ? (
          <span>
            {value}
            {row.correction && (
              <span
                title={`Corrected from "${String(row.correction.original_value ?? "")}" on ${new Date(row.correction.created_at).toLocaleString()}`}
                className="ml-1.5 inline-flex items-center gap-0.5 text-[11px] font-medium text-primary"
              >
                <History className="h-3 w-3" />
                corrected
              </span>
            )}
          </span>
        ) : (
          <span className="text-xs italic text-text-muted">
            {row.status === "not_found" ? "Not found in document" : "No value captured"}
          </span>
        )}
      </td>
      <td className="whitespace-nowrap px-3 py-2.5 align-top sm:px-4">
        <ConfidenceCell row={row} />
      </td>
      <td className="whitespace-nowrap px-3 py-2.5 align-top text-xs font-medium text-foreground sm:px-4">
        {row.display_method || methodLabel(row.extraction_method)}
      </td>
      <td className="min-w-[7rem] px-3 py-2.5 align-top text-xs text-text-secondary sm:px-4">
        {row.evidence ? (
          <>
            <span className="font-medium text-foreground">
              p. {row.evidence.page_number}
            </span>
            <p className="mt-0.5 line-clamp-1 text-[11px] text-text-muted">
              {row.evidence.source_reference || "Source evidence"}
            </p>
          </>
        ) : (
          <span className="text-xs text-text-muted">—</span>
        )}
      </td>
      <td className="whitespace-nowrap px-3 py-2.5 align-top sm:px-4">
        <StatusBadge status={row.status} />
      </td>
      <td className="whitespace-nowrap px-3 py-2.5 align-top sm:px-4">
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="inline-flex items-center gap-1 text-xs font-semibold text-success disabled:opacity-60"
              >
                <Check className="h-3.5 w-3.5" />
                Save
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setDraft(value);
                }}
                disabled={saving}
                className="inline-flex items-center gap-1 text-xs font-semibold text-text-secondary"
              >
                <X className="h-3.5 w-3.5" />
                Cancel
              </button>
            </>
          ) : (
            <>
              {row.evidence && onViewSource && (
                <button
                  type="button"
                  onClick={() =>
                    onViewSource({
                      pageNumber: row.evidence!.page_number,
                      highlightText: row.evidence!.source_text || value,
                      label: row.label,
                      value,
                      confidence: row.confidence ?? 0,
                      verified: row.verified,
                    })
                  }
                  className="inline-flex items-center gap-1 text-xs font-semibold text-text-teal hover:text-primary"
                >
                  <Eye className="h-3 w-3" />
                  View Source
                </button>
              )}
              {canEdit && (
                <button
                  type="button"
                  onClick={() => {
                    setDraft(value);
                    setEditing(true);
                  }}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-text-secondary hover:text-primary"
                >
                  <Pencil className="h-3 w-3" />
                  Edit
                </button>
              )}
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function FieldsTable({
  title,
  rows,
  onViewSource,
  onSaveCorrection,
}: FieldsTableProps) {
  if (rows.length === 0) return null;

  return (
    <div className="editorial-card p-5 sm:p-6">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <div className="mt-3 overflow-x-auto rounded-xl border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-surface-soft">
            <tr>
              {["Field", "Value", "Confidence", "Method", "Source", "Validation", "Actions"].map(
                (header) => (
                  <th
                    key={header}
                    className="whitespace-nowrap border-b border-border px-3 py-2.5 text-left text-xs font-semibold text-foreground sm:px-4"
                  >
                    {header}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <FieldTableRow
                key={row.id}
                row={row}
                onViewSource={onViewSource}
                onSaveCorrection={onSaveCorrection}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
