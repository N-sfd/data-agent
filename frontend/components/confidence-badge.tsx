import { AlertTriangle, CheckCircle2 } from "lucide-react";

interface ConfidenceBadgeProps {
  confidence: number;
}

// Step 10 tiers: green >=95% (high confidence), amber 80-94%
// (review suggested), red <80% (human review required).
export default function ConfidenceBadge({
  confidence,
}: ConfidenceBadgeProps) {
  const percent = Math.round(confidence * 100);

  const tier =
    confidence >= 0.95
      ? "high"
      : confidence >= 0.8
        ? "medium"
        : "low";

  const tone =
    tier === "high"
      ? "bg-emerald-50 text-emerald-700"
      : tier === "medium"
        ? "bg-amber-50 text-amber-700"
        : "bg-red-50 text-red-700";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}
    >
      {tier === "high" ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <AlertTriangle className="h-3 w-3" />
      )}
      {percent}%
    </span>
  );
}
