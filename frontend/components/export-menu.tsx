"use client";

import { Download } from "lucide-react";

import { getStructuredOutput } from "@/lib/documents";
import type { MetadataField } from "@/types/document";

interface ExportMenuProps {
  documentId: string;
  filename: string;
  fields: MetadataField[];
}

function downloadBlob(
  content: string,
  mimeType: string,
  filename: string,
) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function ExportMenu({
  documentId,
  filename,
  fields,
}: ExportMenuProps) {
  const disabled = fields.length === 0;

  function exportCsv() {
    const headers = [
      "Field Group",
      "Field",
      "Value",
      "Confidence",
      "Review Status",
    ];

    const lines = [
      headers.join(","),
      ...fields.map((field) =>
        [
          field.field_group,
          field.label,
          field.value,
          field.confidence,
          field.review_status,
        ]
          .map(
            (value) =>
              `"${String(value).replaceAll('"', '""')}"`,
          )
          .join(","),
      ),
    ];

    downloadBlob(
      lines.join("\n"),
      "text/csv;charset=utf-8;",
      `${filename}.csv`,
    );
  }

  async function exportJson() {
    try {
      const data = await getStructuredOutput(documentId);
      downloadBlob(
        JSON.stringify(data, null, 2),
        "application/json",
        `${filename}.json`,
      );
    } catch {
      // Nothing to export yet — non-fatal, no fields resolved.
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500">
        <Download className="h-3.5 w-3.5" />
        Export
      </span>

      <button
        type="button"
        onClick={exportCsv}
        disabled={disabled}
        className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        CSV
      </button>

      <button
        type="button"
        onClick={exportJson}
        disabled={disabled}
        className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        JSON
      </button>

      <span
        title="Coming soon"
        className="cursor-not-allowed rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-400"
      >
        Excel
      </span>

      <span
        title="Coming soon"
        className="cursor-not-allowed rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-400"
      >
        API
      </span>
    </div>
  );
}
