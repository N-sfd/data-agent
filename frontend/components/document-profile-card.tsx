import { FileStack } from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import type { ContractClassification } from "@/types/document";

interface DocumentProfileCardProps {
  classification: ContractClassification;
}

const CATEGORY_LABELS: Record<string, string> = {
  buy_side: "Buy-side Contract",
  sell_side: "Sell-side Contract",
  unknown: "Unknown",
};

export default function DocumentProfileCard({
  classification,
}: DocumentProfileCardProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <FileStack className="h-4 w-4 text-blue-600" />
        <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
          Document Profile
        </p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <Field label="Type" value={classification.document_type} />

        <Field
          label="Category"
          value={
            CATEGORY_LABELS[classification.contract_side] ??
            classification.contract_side
          }
        />

        <Field
          label="Language"
          value={classification.language ?? "Unknown"}
        />

        <div>
          <span className="text-xs text-slate-400">Confidence</span>
          <div className="mt-1">
            <ConfidenceBadge confidence={classification.confidence} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs text-slate-400">{label}</span>
      <p className="mt-1 truncate text-sm font-medium text-slate-800">
        {value}
      </p>
    </div>
  );
}
