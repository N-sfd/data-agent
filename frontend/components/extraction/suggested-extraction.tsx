"use client";

import { Check } from "lucide-react";

import type { ResolvedSuggestionGroup } from "@/lib/suggestion-groups";

interface SuggestedExtractionProps {
  groups: ResolvedSuggestionGroup[];
  selectedIds: Set<string>;
  disabled?: boolean;
  onToggleGroup: (targetIds: string[]) => void;
  fieldCount: number;
  tableCount: number;
  onSelectAllFields: () => void;
  onSelectAllTables: () => void;
  allFieldsSelected: boolean;
  allTablesSelected: boolean;
}

function CheckboxRow({
  label,
  selected,
  disabled,
  onToggle,
  count,
}: {
  label: string;
  selected: boolean;
  disabled?: boolean;
  onToggle: () => void;
  count?: number;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onToggle}
      className={[
        "flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition",
        selected ? "bg-primary/8" : "hover:bg-surface-soft",
        disabled ? "opacity-50" : "",
      ].join(" ")}
    >
      <span
        className={[
          "flex h-4 w-4 shrink-0 items-center justify-center rounded border",
          selected ? "border-primary bg-primary" : "border-border bg-surface",
        ].join(" ")}
      >
        {selected && <Check className="h-3 w-3 text-white" />}
      </span>
      <span className="min-w-0 flex-1 text-sm font-medium text-foreground">
        {label}
      </span>
      {typeof count === "number" && (
        <span className="text-xs text-text-muted">{count}</span>
      )}
    </button>
  );
}

export default function SuggestedExtraction({
  groups,
  selectedIds,
  disabled = false,
  onToggleGroup,
  fieldCount,
  tableCount,
  onSelectAllFields,
  onSelectAllTables,
  allFieldsSelected,
  allTablesSelected,
}: SuggestedExtractionProps) {
  if (groups.length === 0) {
    return null;
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="border-b border-border bg-surface-soft px-3 py-2.5">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Suggested extraction
        </p>
      </div>

      <div className="p-2">
        {groups.map((group) => {
          const selected =
            group.targetIds.length > 0 &&
            group.targetIds.every((id) => selectedIds.has(id));
          return (
            <CheckboxRow
              key={group.id}
              label={group.label}
              selected={selected}
              disabled={disabled}
              count={group.targetIds.length}
              onToggle={() => onToggleGroup(group.targetIds)}
            />
          );
        })}
      </div>

      <div className="border-t border-border p-2">
        <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Other
        </p>
        {fieldCount > 0 && (
          <CheckboxRow
            label="All Detected Fields"
            selected={allFieldsSelected}
            disabled={disabled}
            count={fieldCount}
            onToggle={onSelectAllFields}
          />
        )}
        {tableCount > 0 && (
          <CheckboxRow
            label="All Tables"
            selected={allTablesSelected}
            disabled={disabled}
            count={tableCount}
            onToggle={onSelectAllTables}
          />
        )}
      </div>
    </div>
  );
}
