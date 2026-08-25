import type { UnifiedTargetOption } from "@/lib/detection";

interface ExtractionTargetSelectorProps {
  options: UnifiedTargetOption[];
  value: string | null;
  disabled?: boolean;
  otherGroupLabel?: string;
  onChange: (key: string) => void;
}

export default function ExtractionTargetSelector({
  options,
  value,
  disabled = false,
  otherGroupLabel = "Other detected",
  onChange,
}: ExtractionTargetSelectorProps) {
  const named = options.filter(
    (option) => option.kind === "named" || option.kind === "template",
  );
  const grouped = options.filter((option) => option.kind === "grouped");
  const custom = options.filter((option) => option.kind === "custom");

  return (
    <label className="block text-xs font-medium text-slate-500">
      Extraction Target
      <select
        value={value ?? ""}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
      >
        {named.length > 0 && (
          <optgroup label="Named">
            {named.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </optgroup>
        )}

        {grouped.length > 0 && (
          <optgroup label={otherGroupLabel}>
            {grouped.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </optgroup>
        )}

        {custom.length > 0 && (
          <optgroup label="Custom">
            {custom.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </optgroup>
        )}
      </select>
    </label>
  );
}
