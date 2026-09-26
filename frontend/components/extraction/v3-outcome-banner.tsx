"use client";

import { AlertTriangle, CheckCircle2, FileQuestion, Info, XCircle } from "lucide-react";

import type { V3ExtractionOutcome } from "@/lib/v3-export";

const TONE: Record<string, { box: string; icon: typeof Info }> = {
  populated: { box: "border-success/30 bg-success/10 text-success", icon: CheckCircle2 },
  needs_review: { box: "border-warning/30 bg-warning/10 text-warning", icon: AlertTriangle },
  no_supported_fields: { box: "border-border bg-surface-soft text-text-secondary", icon: FileQuestion },
  special_source: { box: "border-warning/30 bg-warning/10 text-warning", icon: AlertTriangle },
  failed: { box: "border-danger/30 bg-danger/10 text-danger", icon: XCircle },
  pending: { box: "border-border bg-surface-soft text-text-secondary", icon: Info },
};

/** Explains the document's extraction outcome (backend
 * app/services/extraction_outcome.py) so an empty workbook is never shown
 * without a reason. */
export default function V3OutcomeBanner({ outcome }: { outcome: V3ExtractionOutcome }) {
  const tone = TONE[outcome.status] ?? TONE.pending;
  const Icon = tone.icon;
  return (
    <div role="status" className={`flex gap-3 rounded-xl border p-4 ${tone.box}`}>
      <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-1">
        <p className="text-sm font-semibold">{outcome.title}</p>
        <p className="text-sm text-foreground">{outcome.message}</p>
        {outcome.details.length > 0 && (
          <ul className="list-disc space-y-0.5 pl-5 text-xs text-text-secondary">
            {outcome.details.map((detail) => (
              <li key={detail} className="break-words">
                {detail}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
