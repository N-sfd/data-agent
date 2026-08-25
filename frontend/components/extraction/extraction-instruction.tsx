interface ExtractionInstructionProps {
  value: string;
  disabled?: boolean;
  expanded: boolean;
  onChange: (value: string) => void;
  onToggleExpand: () => void;
}

export default function ExtractionInstruction({
  value,
  disabled = false,
  expanded,
  onChange,
  onToggleExpand,
}: ExtractionInstructionProps) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-500">
        Instruction
        <textarea
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          rows={expanded ? 8 : 3}
          style={{ minHeight: "110px", resize: "vertical" }}
          placeholder="Describe what to extract, or pick a target above to prefill this."
          className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
        />
      </label>

      <button
        type="button"
        onClick={onToggleExpand}
        className="mt-1.5 text-xs font-medium text-blue-700 hover:text-blue-800"
      >
        {expanded ? "Collapse instruction" : "Expand instruction"}
      </button>
    </div>
  );
}
