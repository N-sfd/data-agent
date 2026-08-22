"use client";

import { useState } from "react";

import { CheckCircle2, ChevronDown, ChevronRight } from "lucide-react";

interface IngestionChecklistProps {
  steps: string[];
}

export default function IngestionChecklist({
  steps,
}: IngestionChecklistProps) {
  const [expanded, setExpanded] = useState(false);

  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full items-center justify-between gap-2"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          Ingestion complete
          <span className="font-normal text-slate-500">
            &middot; {steps.length} check{steps.length === 1 ? "" : "s"}{" "}
            passed
          </span>
        </span>

        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
        )}
      </button>

      {expanded && (
        <ol className="mt-4 space-y-2">
          {steps.map((step, index) => (
            <li
              key={`${index}-${step}`}
              className="flex items-start gap-2 text-sm text-slate-700"
            >
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              {step}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
