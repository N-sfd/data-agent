import { Tag } from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import type { ContractClassification } from "@/types/document";

interface ClassificationCardProps {
  classification: ContractClassification;
}

const CONTRACT_SIDE_LABELS: Record<string, string> = {
  buy_side: "Buy-Side",
  sell_side: "Sell-Side",
  unknown: "Unknown",
};

export default function ClassificationCard({
  classification,
}: ClassificationCardProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-50">
          <Tag className="h-6 w-6 text-blue-600" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
            Document Classification
          </p>

          <div className="mt-1 flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-950">
              {classification.document_type}
            </h2>

            <ConfidenceBadge
              confidence={classification.confidence}
            />
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Info
          label="Industry"
          value={classification.industry ?? "Unknown"}
        />

        <Info
          label="Contract Side"
          value={
            CONTRACT_SIDE_LABELS[
              classification.contract_side
            ] ?? classification.contract_side
          }
        />

        <Info
          label="Language"
          value={classification.language ?? "Unknown"}
        />
      </div>
    </div>
  );
}

function Info({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <span className="text-xs text-slate-400">{label}</span>

      <p className="mt-1 truncate text-sm font-medium text-slate-800">
        {value}
      </p>
    </div>
  );
}
