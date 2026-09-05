"use client";

import { AlertTriangle } from "lucide-react";

import type { FieldRow } from "@/components/extraction/field-row";

interface ValidationIssuesPanelProps {
  rows: FieldRow[];
  onIssueClick?: (rowId: string) => void;
}

const ISSUE_COPY: Partial<Record<FieldRow["status"], string>> = {
  not_found: "Missing — selected but not found in the document",
  validation_failed: "Unverified — value could not be confirmed against source text",
  low_confidence: "Low confidence — needs manual review",
  empty: "Empty — resolved but no value was captured",
};

export default function ValidationIssuesPanel({
  rows,
  onIssueClick,
}: ValidationIssuesPanelProps) {
  const issues = rows.filter((row) => row.status !== "extracted");

  if (issues.length === 0) {
    return (
      <div className="editorial-card flex items-center gap-2 p-5 text-sm text-text-secondary sm:p-6">
        <AlertTriangle className="h-4 w-4 text-success" />
        No validation issues — every selected field resolved cleanly.
      </div>
    );
  }

  return (
    <div className="editorial-card p-5 sm:p-6">
      <h3 className="text-sm font-semibold text-foreground">
        Validation issues
        <span className="ml-2 text-xs font-normal text-text-secondary">
          {issues.length} field{issues.length === 1 ? "" : "s"} need attention
        </span>
      </h3>
      <ul className="mt-3 divide-y divide-border rounded-xl border border-border">
        {issues.map((row) => (
          <li key={row.id}>
            <button
              type="button"
              onClick={() => onIssueClick?.(row.id)}
              className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left hover:bg-surface-soft"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{row.label}</p>
                <p className="mt-0.5 text-xs text-text-secondary">
                  {ISSUE_COPY[row.status]}
                </p>
              </div>
              <span className="shrink-0 text-xs font-semibold text-text-teal">
                Review
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
