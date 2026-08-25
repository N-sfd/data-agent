import { DETECTION_TYPE_LABELS } from "@/lib/detection";
import type { DetectionExtractionType } from "@/types/document";

interface ExtractionTypeSelectorProps {
  types: DetectionExtractionType[];
  value: DetectionExtractionType | null;
  disabled?: boolean;
  onChange: (type: DetectionExtractionType) => void;
}

export default function ExtractionTypeSelector({
  types,
  value,
  disabled = false,
  onChange,
}: ExtractionTypeSelectorProps) {
  return (
    <label className="block text-xs font-medium text-slate-500">
      Extraction Type
      <select
        value={value ?? ""}
        disabled={disabled}
        onChange={(event) =>
          onChange(event.target.value as DetectionExtractionType)
        }
        className="mt-1.5 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
      >
        {types.map((type) => (
          <option key={type} value={type}>
            {DETECTION_TYPE_LABELS[type]}
          </option>
        ))}
      </select>
    </label>
  );
}
