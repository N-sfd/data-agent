"use client";

import {
  CheckCircle2,
  HelpCircle,
  Search,
  Sparkles,
  Table2,
} from "lucide-react";

import FieldResult from "@/components/extraction/field-result";
import TableResult from "@/components/extraction/table-result";
import type { UniversalExtractionResult } from "@/types/document";

interface UniversalResultsProps {
  result: UniversalExtractionResult;
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
          <div className="mt-4">
            <FieldResult values={result.values} />
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
            <TableResult key={table.table_id} table={table} />
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
