"use client";

import { Download } from "lucide-react";

import {
  downloadDocumentExportCsv,
  getDocumentExport,
} from "@/lib/reviewed-export";
import { downloadJson } from "@/lib/export";
import type { MetadataField } from "@/types/document";

interface ExportMenuProps {
  documentId: string;
  filename: string;
  fields: MetadataField[];
}

export default function ExportMenu({
  documentId,
  filename,
  fields,
}: ExportMenuProps) {
  const disabled = fields.length === 0;

  async function exportCsv() {
    try {
      await downloadDocumentExportCsv(documentId, `${filename}.csv`);
    } catch {
      // Non-fatal — export may fail if fields were never persisted.
    }
  }

  async function exportJson() {
    try {
      const data = await getDocumentExport(documentId);
      downloadJson(`${filename}.json`, data.fields);
    } catch {
      // Nothing to export yet — non-fatal.
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
        onClick={() => void exportCsv()}
        disabled={disabled}
        className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        CSV
      </button>

      <button
        type="button"
        onClick={() => void exportJson()}
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
        title="Use /api/documents/{id}/export and /oracle-payload"
        className="cursor-help rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-400"
      >
        API
      </span>
    </div>
  );
}
