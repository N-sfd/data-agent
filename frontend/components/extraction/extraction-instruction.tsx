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
      <label className="block text-xs font-medium text-text-muted">
        Instruction
        <textarea
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          rows={expanded ? 8 : 3}
          style={{ minHeight: "110px", resize: "vertical" }}
          placeholder="Describe what to extract when it isn’t in the detected schema."
          className="mt-1.5 w-full rounded-xl border border-border bg-surface p-4 text-sm text-foreground outline-none transition placeholder:text-text-muted focus:border-primary/30 focus:ring-2 focus:ring-primary/10 disabled:bg-surface-soft"
        />
      </label>

      <button
        type="button"
        onClick={onToggleExpand}
        className="mt-1.5 text-xs font-medium text-text-teal hover:text-primary"
      >
        {expanded ? "Collapse instruction" : "Expand instruction"}
      </button>
    </div>
  );
}
