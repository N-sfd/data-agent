"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import {
  ReviewStatusBadge,
  cellSourceRequest,
  formatCellValue,
  locationLabel,
} from "@/components/staging/review-status";
import {
  getStagingRecord,
  type StagingDataset,
  type StagingRecord,
} from "@/lib/staging-workbook";

interface StagingRecordDrawerProps {
  documentId: string;
  dataset: StagingDataset;
  record: StagingRecord;
  onClose: () => void;
  onOpenSource?: (request: SourceViewRequest) => void;
}

const LONG_VALUE = 400;

/** Every field of one record — value, review state, reasons and source
 * evidence. Compact datasets fetch the full record on open; others already
 * hold it. Profile-agnostic: labels and order come from the dataset. */
export default function StagingRecordDrawer({
  documentId,
  dataset,
  record,
  onClose,
  onOpenSource,
}: StagingRecordDrawerProps) {
  const [loaded, setLoaded] = useState<{ id: string; record: StagingRecord | null; error: string | null } | null>(
    null,
  );

  useEffect(() => {
    if (!dataset.compact) return;
    let cancelled = false;
    getStagingRecord(documentId, dataset.dataset_id, record.record_id)
      .then((full) => {
        if (!cancelled) setLoaded({ id: record.record_id, record: full, error: null });
      })
      .catch(() => {
        if (!cancelled) setLoaded({ id: record.record_id, record: null, error: "Unable to load this record." });
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, dataset.compact, dataset.dataset_id, record.record_id]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const current = loaded && loaded.id === record.record_id ? loaded : null;
  const full = dataset.compact ? current?.record ?? null : record;
  const title = dataset.identity_fields
    .map((field) => record.cells[field])
    .filter((cell) => cell && cell.value != null)
    .map((cell) => formatCellValue(cell))
    .slice(0, 2)
    .join(" · ");

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label="Evidence">
      <button type="button" aria-label="Close details" className="flex-1 bg-black/20" onClick={onClose} />
      <aside className="flex h-full w-full max-w-2xl flex-col border-l border-border bg-surface shadow-xl">
        <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-teal">{dataset.display_name}</p>
            <h4 className="mt-1 break-words text-sm font-semibold text-foreground">{title || record.record_id}</h4>
          </div>
          <div className="flex items-center gap-2">
            <ReviewStatusBadge status={record.record_status} />
            <button type="button" onClick={onClose} className="rounded-md p-1 text-text-secondary hover:bg-surface-soft" aria-label="Close">
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>
        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4 text-sm">
          {dataset.compact && !current && <p className="text-text-muted">Loading record...</p>}
          {current?.error && <p className="text-danger">{current.error}</p>}
          {full &&
            dataset.columns.map((column) => {
              const cell = full.cells[column.canonical_field];
              if (!cell) return null;
              const text = formatCellValue(cell);
              const requestId = `${dataset.dataset_id}:${full.record_id}:${column.canonical_field}`;
              const request = cellSourceRequest(cell, requestId);
              return (
                <section key={column.canonical_field} className="rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">{column.display_label}</p>
                    <ReviewStatusBadge status={cell.review_status} />
                  </div>
                  {text ? (
                    <p
                      className={`mt-1 whitespace-pre-wrap break-words text-foreground ${
                        text.length > LONG_VALUE ? "max-h-72 overflow-y-auto rounded bg-surface-soft p-2 text-xs" : ""
                      }`}
                    >
                      {text}
                    </p>
                  ) : (
                    <p className="mt-1 text-text-muted">—</p>
                  )}
                  {cell.review_reasons.length > 0 && (
                    <ul className="mt-1 list-disc pl-5 text-xs text-warning">
                      {cell.review_reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  )}
                  {cell.provenance && text && (
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-secondary">
                      <span>Location: {locationLabel(cell)}</span>
                      {cell.provenance.source_locator?.element_id && (
                        <span className="font-mono">#{cell.provenance.source_locator.element_id}</span>
                      )}
                      {request && onOpenSource && (
                        <button
                          type="button"
                          onClick={() => onOpenSource(request)}
                          className="font-medium text-primary hover:underline"
                        >
                          View source evidence
                        </button>
                      )}
                    </div>
                  )}
                </section>
              );
            })}
        </div>
      </aside>
    </div>
  );
}
