import type { DetectionCounts } from "@/types/document";
import {
  DETECTION_COUNT_KEYS,
  DETECTION_TYPE_LABELS,
  DETECTION_TYPE_PLURAL,
} from "@/lib/detection";

interface DetectionCountChipsProps {
  counts: DetectionCounts;
  tableTotal?: number;
  className?: string;
}

export default function DetectionCountChips({
  counts,
  tableTotal,
  className,
}: DetectionCountChipsProps) {
  const chips = (
    Object.keys(DETECTION_COUNT_KEYS) as Array<keyof DetectionCounts>
  ).flatMap((key) => {
    const value = key === "tables" && tableTotal !== undefined
      ? tableTotal
      : counts[key];

    if (!value) return [];

    const type = DETECTION_COUNT_KEYS[key];
    const label = value === 1
      ? DETECTION_TYPE_LABELS[type]
      : DETECTION_TYPE_PLURAL[type];

    return [{ key, value, label }];
  });

  if (chips.length === 0) {
    return null;
  }

  return (
    <div className={["flex flex-wrap gap-2", className].filter(Boolean).join(" ")}>
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex items-center gap-1.5 rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800"
        >
          {chip.value} {chip.label}
        </span>
      ))}
    </div>
  );
}
