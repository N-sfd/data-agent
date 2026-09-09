"use client";

import type { ExtractTargetsResult } from "@/types/document";

interface ExtractionSummaryBarProps {
  result: ExtractTargetsResult;
  requestedCount?: number;
}

/**
 * Post-extraction summary: requested / resolved / not present / needs review.
 * Unresolved items are treated as "not present", not fatal errors.
 */
export default function ExtractionSummaryBar({
  result,
  requestedCount,
}: ExtractionSummaryBarProps) {
  const resolved = result.scalars.length + result.tables.length;
  const notPresent = result.unresolved_targets.length;
  const needsReview = result.scalars.filter(
    (s) => !s.verified || s.confidence_band === "low",
  ).length;
  const requested =
    requestedCount ?? resolved + notPresent;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-border bg-surface-soft/70 px-4 py-2.5 text-xs text-text-secondary">
      <span>
        <span className="font-semibold text-foreground">{requested}</span>{" "}
        requested
      </span>
      <span>
        <span className="font-semibold text-success">{resolved}</span> resolved
      </span>
      {notPresent > 0 && (
        <span>
          <span className="font-semibold text-text-secondary">{notPresent}</span>{" "}
          not present
        </span>
      )}
      {needsReview > 0 && (
        <span>
          <span className="font-semibold text-warning">{needsReview}</span> need
          review
        </span>
      )}
    </div>
  );
}
