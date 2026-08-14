"use client";

import { useState } from "react";
import {
  CheckCircle2,
  Download,
  Eye,
  FileText,
  HelpCircle,
  Search,
  Sparkles,
  Table2,
} from "lucide-react";

import type {
  UniversalExtractionResult,
  UniversalTable,
  UniversalValue,
} from "@/types/document";

interface UniversalResultsProps {
  result: UniversalExtractionResult;
}

function methodLabel(method: string): string {
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
    default:
      return method;
  }
}

function ExtractionMethodBadge({
  item,
}: {
  item: UniversalValue;
}) {
  const isAi = item.extraction_method === "ai";

  if (isAi) {
    return (
      <div className="space-y-1.5">
        <p className="text-xs text-slate-400">
          Extraction method
        </p>
        <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-violet-700">
          <Sparkles className="h-3.5 w-3.5" />
          AI-assisted
        </p>
        {item.verified ? (
          <p className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Verified against source
          </p>
        ) : (
          <p className="text-xs font-medium text-amber-700">
            Not yet verified against source
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <p className="text-xs text-slate-400">
        Extraction method
      </p>
      <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-700">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Deterministic
      </p>
      <p className="text-xs text-slate-500">
        {methodLabel(item.extraction_method)}
      </p>
      {item.verified && (
        <p className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Verified against source
        </p>
      )}
    </div>
  );
}

function ResultMethodSummary({
  result,
}: {
  result: UniversalExtractionResult;
}) {
  const hasAi = result.values.some(
    (item) => item.extraction_method === "ai",
  ) || Boolean(result.answer);

  const verifiedAiCount = result.values.filter(
    (item) =>
      item.extraction_method === "ai" && item.verified,
  ).length;

  if (hasAi) {
    return (
      <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-violet-700">
          Extraction method
        </p>
        <p className="mt-1 inline-flex items-center gap-1.5 text-sm font-semibold text-violet-900">
          <Sparkles className="h-4 w-4" />
          AI-assisted
        </p>
        {verifiedAiCount > 0 && (
          <p className="mt-1 inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Source verified
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
        Extraction method
      </p>
      <p className="mt-1 inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-900">
        <CheckCircle2 className="h-4 w-4" />
        Deterministic
      </p>
    </div>
  );
}

function ValueCard({ item }: { item: UniversalValue }) {
  const [showSource, setShowSource] = useState(false);

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {item.label}
      </p>

      <p className="mt-2 text-lg font-semibold text-slate-950">
        {String(item.value ?? "")}
      </p>

      <div className="mt-4 grid gap-4 text-xs text-slate-600 sm:grid-cols-2">
        <div>
          <span className="text-slate-400">Source</span>
          <p className="mt-1 font-medium text-slate-800">
            Page {item.evidence.page_number}
          </p>
        </div>

        <ExtractionMethodBadge item={item} />
      </div>

      <button
        type="button"
        onClick={() => setShowSource((value) => !value)}
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700 hover:text-blue-800"
      >
        <Eye className="h-3.5 w-3.5" />
        {showSource ? "Hide Source" : "View Source"}
      </button>

      {showSource && (
        <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-600">
          <p className="font-medium text-slate-800">
            {item.evidence.source_reference}
          </p>
          <p className="mt-2 whitespace-pre-wrap">
            {item.evidence.source_text}
          </p>
        </div>
      )}
    </div>
  );
}

function TableCard({ table }: { table: UniversalTable }) {
  function exportCsv() {
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

    const blob = new Blob([lines.join("\n")], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `table-page-${table.page_number}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-6 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Extracted table
          </p>
          <p className="mt-1 font-semibold text-slate-900">
            Page {table.page_number}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {table.source_reference}
          </p>
        </div>

        <div className="flex gap-2">
          <a
            href={`#page-${table.page_number}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <FileText className="h-3.5 w-3.5" />
            View Page {table.page_number}
          </a>

          <button
            type="button"
            onClick={exportCsv}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
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

export default function UniversalResults({
  result,
}: UniversalResultsProps) {
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
            <Search className="h-5 w-5 text-blue-600" />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
              Universal extraction
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-950">
              {result.instruction}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Intent: {result.intent} · Pages used:{" "}
              {result.pages_used.join(", ") || "none"}
            </p>
          </div>
        </div>

        <ResultMethodSummary result={result} />

        {result.warnings.length > 0 && (
          <div className="mt-4 space-y-2">
            {result.warnings.map((warning) => (
              <div
                key={warning}
                className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
              >
                {warning}
              </div>
            ))}
          </div>
        )}
      </div>

      {result.answer && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50">
              <HelpCircle className="h-5 w-5 text-violet-600" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Answer
              </p>
              <p className="mt-1 text-sm text-slate-500">
                Question
              </p>
              <p className="mt-1 font-medium text-slate-900">
                {result.instruction}
              </p>
              <p className="mt-4 text-base leading-7 text-slate-800">
                {result.answer}
              </p>
              <div className="mt-4 rounded-xl border border-violet-200 bg-violet-50 px-3 py-2">
                <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-violet-800">
                  <Sparkles className="h-3.5 w-3.5" />
                  AI-assisted
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {result.values.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Extracted data
          </p>
          <div className="mt-4 space-y-3">
            {result.values.map((item, index) => (
              <ValueCard
                key={`${item.label}-${index}`}
                item={item}
              />
            ))}
          </div>
        </div>
      )}

      {result.tables.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 px-1">
            <Table2 className="h-4 w-4 text-slate-500" />
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Extracted tables
            </p>
          </div>

          {result.tables.map((table) => (
            <TableCard key={table.table_id} table={table} />
          ))}
        </div>
      )}

      {result.unresolved_requests.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
          <p className="font-medium text-slate-800">
            Unresolved requests
          </p>
          <p className="mt-1">
            {result.unresolved_requests.join(", ")}
          </p>
        </div>
      )}

      {result.values.length === 0 &&
        result.tables.length === 0 &&
        !result.answer && (
          <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">
            <Table2 className="mx-auto h-9 w-9 text-slate-300" />
            <p className="mt-3 font-medium text-slate-700">
              No structured results yet
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Try a more specific field, page range, or table request.
            </p>
          </div>
        )}
    </div>
  );
}
