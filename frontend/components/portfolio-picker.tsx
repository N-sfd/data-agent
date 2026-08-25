"use client";

import { useEffect } from "react";
import { FileStack } from "lucide-react";

import { formatBytes } from "@/lib/format";
import type { EmbeddedFileSummary } from "@/types/document";

interface PortfolioPickerProps {
  files: EmbeddedFileSummary[];
  busy?: boolean;
  onSelect: (filename: string) => void;
  onCancel: () => void;
}

export default function PortfolioPicker({
  files,
  busy = false,
  onSelect,
  onCancel,
}: PortfolioPickerProps) {
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
        aria-labelledby="portfolio-picker-title"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
      >
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-100">
            <FileStack className="h-5 w-5 text-blue-700" />
          </div>

          <div className="min-w-0">
            <p
              id="portfolio-picker-title"
              className="text-sm font-semibold text-blue-700"
            >
              PDF Portfolio detected
            </p>

            <h2 className="mt-1 text-lg font-semibold text-slate-950">
              This PDF contains {files.length} embedded documents
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Choose which one to analyze.
            </p>
          </div>
        </div>

        <div className="mt-5 max-h-64 space-y-1.5 overflow-y-auto">
          {files.map((file) => (
            <button
              key={file.filename}
              type="button"
              disabled={busy}
              onClick={() => onSelect(file.filename)}
              className="flex w-full items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-left transition hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="truncate text-sm font-medium text-slate-800">
                {file.filename}
              </span>
              <span className="ml-3 shrink-0 text-xs text-slate-500">
                {formatBytes(file.size_bytes)}
              </span>
            </button>
          ))}
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
