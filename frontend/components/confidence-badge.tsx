import ConfidenceIndicator from "@/components/confidence-indicator";

interface ConfidenceBadgeProps {
  confidence: number;
}

export default function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  return <ConfidenceIndicator confidence={confidence} />;
}
