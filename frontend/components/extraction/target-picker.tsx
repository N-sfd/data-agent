"use client";

import { Check, Search } from "lucide-react";
import { useMemo, useState } from "react";

import {
  displayGroupLabel,
  filterTargets,
  groupTargets,
} from "@/lib/target-groups";
import type { DocumentTarget, TargetType } from "@/types/document";

export interface CustomQuickPick {
  key: string;
  label: string;
  prompt: string;
}

interface TargetPickerProps {
  targets: DocumentTarget[];
  customQuickPicks: CustomQuickPick[];
  selectedIds: Set<string>;
  disabled?: boolean;
  onToggle: (targetId: string) => void;
  onSelectAll: (targetType: TargetType) => void;
  onClear: () => void;
  onSelectCustom: (pick: CustomQuickPick) => void;
}

function confidenceLabel(target: DocumentTarget): string {
  const pct = Math.round(target.confidence * 100);
  const page = target.page_numbers[0];
  return page ? `${pct}% confidence · page ${page}` : `${pct}% confidence`;
}

export default function TargetPicker({
  targets,
  customQuickPicks,
  selectedIds,
  disabled = false,
  onToggle,
  onSelectAll,
  onClear,
  onSelectCustom,
}: TargetPickerProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () => filterTargets(targets, query),
    [targets, query],
  );
  const grouped = useMemo(() => groupTargets(filtered), [filtered]);
  const hasAnyDetected = targets.length > 0;
  const fieldCount = targets.filter((t) => t.target_type === "field").length;
  const tableCount = targets.filter((t) => t.target_type === "table").length;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border bg-surface-soft px-3">
        <Search className="h-4 w-4 shrink-0 text-text-muted" />
        <input
          type="text"
          value={query}
          disabled={disabled}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search this document’s schema..."
          className="flex-1 bg-transparent py-3 text-sm text-foreground outline-none placeholder:text-text-muted disabled:opacity-50"
        />
        {hasAnyDetected && (
          <span className="shrink-0 text-[11px] font-medium text-text-muted">
            {targets.length} detected
          </span>
        )}
      </div>

      <div className="max-h-80 overflow-y-auto p-2">
        {hasAnyDetected &&
          Array.from(grouped.entries()).map(([groupKey, groupTargetsList]) => (
            <section key={groupKey} className="mb-1">
              <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                {displayGroupLabel(groupKey)}
              </p>
              {groupTargetsList.map((target) => {
                const selected = selectedIds.has(target.id);
                return (
                  <button
                    key={target.id}
                    type="button"
                    disabled={disabled}
                    onClick={() => onToggle(target.id)}
                    className={[
                      "flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition disabled:opacity-50",
                      selected
                        ? "bg-primary/8 hover:bg-primary/12"
                        : "hover:bg-surface-soft",
                    ].join(" ")}
                  >
                    <span
                      className={[
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                        selected
                          ? "border-primary bg-primary"
                          : "border-border bg-surface",
                      ].join(" ")}
                    >
                      {selected && <Check className="h-3 w-3 text-white" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-foreground">
                        {target.label}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-text-secondary">
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-success" />
                        {confidenceLabel(target)}
                      </span>
                    </span>
                  </button>
                );
              })}
            </section>
          ))}

        {!hasAnyDetected && (
          <p className="px-2 py-6 text-center text-sm text-text-secondary">
            No structures were detected in this document yet. Use a custom
            instruction below, or wait for schema discovery to finish.
          </p>
        )}

        {hasAnyDetected && filtered.length === 0 && (
          <p className="px-2 py-6 text-center text-sm text-text-secondary">
            No detected items match &ldquo;{query}&rdquo;.
          </p>
        )}

        <section className="mt-1 border-t border-border pt-2">
          <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            Custom
          </p>
          <div className="flex flex-wrap gap-2 px-2 pb-1">
            {customQuickPicks.map((pick) => (
              <button
                key={pick.key}
                type="button"
                disabled={disabled}
                onClick={() => onSelectCustom(pick)}
                className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text-secondary transition hover:border-accent/40 hover:bg-accent/5 hover:text-accent disabled:opacity-50"
              >
                {pick.label}
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border p-3">
        <button
          type="button"
          disabled={disabled || selectedIds.size === 0}
          onClick={onClear}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-text-muted transition hover:text-foreground disabled:opacity-40"
        >
          Clear
        </button>
        <div className="flex-1" />
        <button
          type="button"
          disabled={disabled || fieldCount === 0}
          onClick={() => onSelectAll("field")}
          className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-soft disabled:opacity-40"
        >
          Extract All Fields{fieldCount ? ` (${fieldCount})` : ""}
        </button>
        <button
          type="button"
          disabled={disabled || tableCount === 0}
          onClick={() => onSelectAll("table")}
          className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-soft disabled:opacity-40"
        >
          Extract All Tables{tableCount ? ` (${tableCount})` : ""}
        </button>
      </div>
    </div>
  );
}
