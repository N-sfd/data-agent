"use client";

import { useState } from "react";
import { Check, Pencil, X, XCircle } from "lucide-react";

import type { FieldRow } from "@/components/extraction/field-row";
import SourceVerificationPanel, {
  type SourceViewRequest,
} from "@/components/source-verification-panel";

interface SourceVerificationDrawerProps {
  open: boolean;
  onClose: () => void;
  documentId: string;
  documentName: string;
  pageCount: number;
  request: SourceViewRequest | null;
  activeRow?: FieldRow | null;
  onSaveCorrection?: (row: FieldRow, correctedValue: string) => Promise<void> | void;
  onMarkVerified?: (row: FieldRow) => Promise<void> | void;
  onReject?: (row: FieldRow) => Promise<void> | void;
}

export default function SourceVerificationDrawer({
  open,
  onClose,
  documentId,
  documentName,
  pageCount,
  request,
  activeRow = null,
  onSaveCorrection,
  onMarkVerified,
  onReject,
}: SourceVerificationDrawerProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const displayValue =
    activeRow?.correction?.corrected_value ??
    activeRow?.value ??
    request?.value ??
    "";
  const machineValue =
    activeRow?.scalar?.extracted_value ??
    activeRow?.correction?.original_value ??
    activeRow?.value ??
    request?.value ??
    "";

  async function run(action: () => Promise<void> | void) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
      setEditing(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close source verification"
        className="absolute inset-0 bg-slate-950/40"
        onClick={onClose}
      />

      <div className="relative flex h-full w-full max-w-xl flex-col bg-surface shadow-2xl sm:max-w-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Source verification
            </p>
            <p className="mt-0.5 truncate text-sm font-medium text-foreground">
              {request?.label ?? activeRow?.label ?? "Field"}
            </p>
            <p className="mt-1 text-sm text-text-secondary">
              <span className="font-medium text-foreground">Value:</span>{" "}
              {String(displayValue || "—")}
            </p>
            <p className="mt-0.5 text-xs text-text-muted">
              Page {request?.pageNumber ?? "—"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-text-muted transition hover:bg-surface-soft hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <SourceVerificationPanel
            documentId={documentId}
            documentName={documentName}
            pageCount={pageCount}
            request={request}
          />

          {activeRow && (
            <div className="space-y-3 border-t border-border px-5 py-4 text-sm">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Raw OCR / evidence
                </p>
                <p className="mt-1 whitespace-pre-wrap text-text-secondary">
                  {activeRow.evidence?.source_text || "—"}
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Machine extracted
                  </p>
                  <p className="mt-1 text-foreground">{String(machineValue || "—")}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Confidence
                  </p>
                  <p className="mt-1 text-foreground">
                    {activeRow.confidence != null
                      ? `${Math.round(activeRow.confidence * 100)}% (${activeRow.confidence_band ?? "—"})`
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Validation
                  </p>
                  <p className="mt-1 text-foreground">
                    {activeRow.scalar?.validation_status ?? activeRow.status}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Extraction method
                  </p>
                  <p className="mt-1 text-foreground">
                    {activeRow.display_method || activeRow.extraction_method || "—"}
                  </p>
                </div>
              </div>

              {editing ? (
                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Edit value
                    <input
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-primary/40"
                    />
                  </label>
                  <p className="text-xs text-text-muted">
                    Machine value is preserved: {String(machineValue || "—")}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy || !onSaveCorrection}
                      className="btn-primary text-xs disabled:opacity-50"
                      onClick={() =>
                        activeRow &&
                        onSaveCorrection &&
                        void run(() => onSaveCorrection(activeRow, draft))
                      }
                    >
                      <Check className="h-3.5 w-3.5" />
                      Save
                    </button>
                    <button
                      type="button"
                      className="btn-secondary text-xs"
                      onClick={() => setEditing(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy || !onMarkVerified || !activeRow}
                    className="btn-primary text-xs disabled:opacity-50"
                    onClick={() =>
                      activeRow &&
                      onMarkVerified &&
                      void run(() => onMarkVerified(activeRow))
                    }
                  >
                    <Check className="h-3.5 w-3.5" />
                    Verify
                  </button>
                  <button
                    type="button"
                    disabled={busy || !onSaveCorrection || !activeRow}
                    className="btn-secondary text-xs disabled:opacity-50"
                    onClick={() => {
                      setDraft(String(displayValue ?? ""));
                      setEditing(true);
                    }}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit
                  </button>
                  <button
                    type="button"
                    disabled={busy || !onReject || !activeRow}
                    className="btn-secondary text-xs text-danger disabled:opacity-50"
                    onClick={() =>
                      activeRow &&
                      onReject &&
                      void run(() => onReject(activeRow))
                    }
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    Reject
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
