"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { formatBytes, formatDate } from "@/lib/format";
import type { ExistingDocumentSummary } from "@/types/document";

interface DuplicateDialogProps {
  existingDocument: ExistingDocumentSummary;
  onUseExisting: () => void;
  onUploadAnyway: () => void;
  onCancel: () => void;
  busy?: boolean;
}

export default function DuplicateDialog({
  existingDocument,
  onUseExisting,
  onUploadAnyway,
  onCancel,
  busy = false,
}: DuplicateDialogProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onCancel();
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="duplicate-dialog-title"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
      >
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100">
            <AlertTriangle className="h-5 w-5 text-amber-700" />
          </div>

          <div className="min-w-0">
            <p
              id="duplicate-dialog-title"
              className="text-sm font-semibold text-amber-700"
            >
              Possible duplicate
            </p>

            <h2 className="mt-1 truncate text-lg font-semibold text-slate-950">
              {existingDocument.original_filename}
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Uploaded: {formatDate(existingDocument.uploaded_at)} ·{" "}
              {formatBytes(existingDocument.size_bytes)}
            </p>

            <p className="mt-2 text-sm text-slate-500">
              Similarity: <span className="font-medium text-slate-800">100%</span>
            </p>

            {!existingDocument.file_available && (
              <p className="mt-2 text-sm text-amber-700">
                The original file for this document is no longer available
                on the server, so it can&apos;t be reused.
              </p>
            )}
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onUploadAnyway}
            disabled={busy}
            className={
              existingDocument.file_available
                ? "rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                : "rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            }
          >
            Upload Anyway
          </button>

          {existingDocument.file_available && (
            <button
              type="button"
              onClick={onUseExisting}
              disabled={busy}
              className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Use Existing
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
