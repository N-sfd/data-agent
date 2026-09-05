"use client";

import { useState } from "react";
import { Check, Copy, Download, FileText } from "lucide-react";

import { downloadBlob, toCsv, toTsv } from "@/lib/export";
import type { UniversalTable } from "@/types/document";

interface TableResultProps {
  table: UniversalTable;
  onViewSource?: (request: {
    pageNumber: number;
    highlightText?: string | null;
    label?: string;
  }) => void;
}

export default function TableResult({ table, onViewSource }: TableResultProps) {
  const [copied, setCopied] = useState(false);

  async function copyTable() {
    try {
      await navigator.clipboard.writeText(toTsv(table.headers, table.rows));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be denied by the browser — the export
      // buttons remain a reliable fallback.
    }
  }

  function exportCsv() {
    downloadBlob(
      toCsv(table.headers, table.rows),
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
    <div className="editorial-card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            {table.title || "Extracted table"}
          </p>
          <p className="mt-1 font-semibold text-foreground">
            Page {table.page_number}
            <span className="ml-2 text-xs font-medium text-text-teal">
              · Source evidence
            </span>
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {table.source_reference || `Verified against page ${table.page_number}`}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {onViewSource ? (
            <button
              type="button"
              onClick={() =>
                onViewSource({
                  pageNumber: table.page_number,
                  highlightText: table.source_reference || null,
                  label: table.title || "Extracted table",
                })
              }
              className="btn-secondary py-1.5 text-xs"
            >
              <FileText className="h-3.5 w-3.5" />
              View Source
            </button>
          ) : (
            <a
              href={`#page-${table.page_number}`}
              className="btn-secondary py-1.5 text-xs"
            >
              <FileText className="h-3.5 w-3.5" />
              View Source
            </a>
          )}

          <button
            type="button"
            onClick={copyTable}
            className="btn-secondary py-1.5 text-xs"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-success" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
            {copied ? "Copied" : "Copy"}
          </button>

          <button
            type="button"
            onClick={exportCsv}
            className="btn-secondary py-1.5 text-xs"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>

          <button
            type="button"
            onClick={exportJson}
            className="btn-secondary py-1.5 text-xs"
          >
            <Download className="h-3.5 w-3.5" />
            Export JSON
          </button>
        </div>
      </div>

      <div className="max-h-[32rem] overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 z-10 bg-surface-soft">
            <tr>
              {table.headers.map((header) => (
                <th
                  key={header}
                  className="whitespace-nowrap border-b border-border bg-surface-soft px-4 py-3 text-left font-semibold text-foreground"
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
                className="border-b border-border last:border-0 hover:bg-surface-soft"
              >
                {table.headers.map((header) => (
                  <td
                    key={header}
                    className="whitespace-nowrap px-4 py-3 text-text-secondary"
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
