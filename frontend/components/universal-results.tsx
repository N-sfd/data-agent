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
  const hasAi =
    result.values.some((item) => item.extraction_method === "ai") ||
    Boolean(result.answer);

  const verifiedAiCount = result.values.filter(
    (item) => item.extraction_method === "ai" && item.verified,
  ).length;

  if (hasAi) {
    return (
      <div className="mt-4 rounded-xl border border-accent/20 bg-accent/5 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">
          Extraction method
        </p>
        <p className="mt-1 inline-flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <Sparkles className="h-4 w-4 text-accent" />
          AI-assisted
        </p>
        {verifiedAiCount > 0 && (
          <p className="mt-1 inline-flex items-center gap-1.5 text-xs font-medium text-success">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Source verified
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-xl border border-success/20 bg-success/5 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-success">
        Extraction method
      </p>
      <p className="mt-1 inline-flex items-center gap-1.5 text-sm font-semibold text-foreground">
        <CheckCircle2 className="h-4 w-4 text-success" />
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
      <div className="editorial-card p-6">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
            <Search className="h-5 w-5 text-primary" />
          </div>

          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-teal">
              Universal extraction
            </p>
            <h2 className="mt-1 text-lg font-medium text-foreground">
              {result.instruction}
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
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
                className="rounded-xl border border-warning/25 bg-warning/5 p-3 text-sm text-warning"
              >
                {warning}
              </div>
            ))}
          </div>
        )}
      </div>

      {result.answer && (
        <div className="editorial-card p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10">
              <HelpCircle className="h-5 w-5 text-accent" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Answer
              </p>
              <p className="mt-1 text-sm text-text-secondary">Question</p>
              <p className="mt-1 font-medium text-foreground">
                {result.instruction}
              </p>
              <p className="mt-4 text-base leading-7 text-foreground">
                {result.answer}
              </p>
              <div className="mt-4 rounded-xl border border-accent/20 bg-accent/5 px-3 py-2">
                <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-accent">
                  <Sparkles className="h-3.5 w-3.5" />
                  AI-assisted
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {result.values.length > 0 && (
        <div className="editorial-card p-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
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
            <Table2 className="h-4 w-4 text-text-muted" />
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Extracted tables
            </p>
          </div>

          {result.tables.map((table) => (
            <TableResult key={table.table_id} table={table} />
          ))}
        </div>
      )}

      {result.unresolved_requests.length > 0 && (
        <div className="editorial-card p-4 text-sm text-text-secondary">
          <p className="font-medium text-foreground">Unresolved requests</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {result.unresolved_requests.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {result.values.length === 0 &&
        result.tables.length === 0 &&
        !result.answer && (
          <div className="editorial-card p-10 text-center">
            <Table2 className="mx-auto h-9 w-9 text-text-muted" />
            <p className="mt-3 font-medium text-foreground">
              No structured results yet
            </p>
            <p className="mt-1 text-sm text-text-secondary">
              Try a more specific field, page range, or table request.
            </p>
          </div>
        )}
    </div>
  );
}
