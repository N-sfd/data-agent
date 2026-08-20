interface ConfidenceIndicatorProps {
  confidence: number;
  showPercent?: boolean;
}

export default function ConfidenceIndicator({
  confidence,
  showPercent = true,
}: ConfidenceIndicatorProps) {
  const percent = Math.round(confidence * 100);

  const dotColor =
    confidence >= 0.95
      ? "bg-success"
      : confidence >= 0.8
        ? "bg-warning"
        : "bg-danger";

  const textColor =
    confidence >= 0.95
      ? "text-success"
      : confidence >= 0.8
        ? "text-warning"
        : "text-danger";

  return (
    <span
      className={`inline-flex items-center gap-2 text-sm ${textColor}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      {showPercent && `${percent}%`}
    </span>
  );
}
