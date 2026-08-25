"use client";

import { useState } from "react";
import { Check, Copy, Download, FileText } from "lucide-react";

import type { UniversalTable } from "@/types/document";

interface TableResultProps {
  table: UniversalTable;
}

function downloadBlob(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function toCsv(table: UniversalTable): string {
  const lines = [
    table.headers.join(","),
    ...table.rows.map((row) =>
      table.headers
        .map((header) => {
          const value = String(row[header] ?? "");
          return `"${value.replaceAll('"', '""')}"`;
        })
        .join(","),
    ),
  ];
  return lines.join("\n");
}

function toTsv(table: UniversalTable): string {
  const lines = [
    table.headers.join("\t"),
    ...table.rows.map((row) =>
      table.headers.map((header) => String(row[header] ?? "")).join("\t"),
    ),
  ];
  return lines.join("\n");
}

export default function TableResult({ table }: TableResultProps) {
  const [copied, setCopied] = useState(false);

  async function copyTable() {
    try {
      await navigator.clipboard.writeText(toTsv(table));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be denied by the browser — the export
      // buttons remain a reliable fallback.
    }
  }

  function exportCsv() {
    downloadBlob(
      toCsv(table),
      `table-page-${table.page_number}.csv`,
      "text/csv;charset=utf-8;",
    );
  }

  function exportJson() {
    downloadBlob(
      JSON.stringify(table.rows, null, 2),
      `table-page-${table.page_number}.json`,
      "application/json;charset=utf-8;",
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-6 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {table.title || "Extracted table"}
          </p>
          <p className="mt-1 font-semibold text-slate-900">
            Page {table.page_number}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {table.source_reference}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <a
            href={`#page-${table.page_number}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <FileText className="h-3.5 w-3.5" />
            View Source
          </a>

          <button
            type="button"
            onClick={copyTable}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-600" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
            {copied ? "Copied" : "Copy"}
          </button>

          <button
            type="button"
            onClick={exportCsv}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>

          <button
            type="button"
            onClick={exportJson}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" />
            Export JSON
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              {table.headers.map((header) => (
                <th
                  key={header}
                  className="whitespace-nowrap border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                {table.headers.map((header) => (
                  <td
                    key={header}
                    className="whitespace-nowrap px-4 py-3 text-slate-700"
                  >
                    {String(row[header] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
