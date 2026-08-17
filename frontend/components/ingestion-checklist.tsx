import { CheckCircle2, ListChecks } from "lucide-react";

interface IngestionChecklistProps {
  steps: string[];
}

export default function IngestionChecklist({
  steps,
}: IngestionChecklistProps) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <ListChecks className="h-4 w-4 text-blue-600" />

        <h2 className="text-sm font-semibold text-slate-950">
          Ingestion pipeline
        </h2>
      </div>

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
    </div>
  );
}
