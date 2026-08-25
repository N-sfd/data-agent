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

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center gap-2 border-b border-slate-100 px-3">
        <Search className="h-4 w-4 shrink-0 text-slate-400" />
        <input
          type="text"
          value={query}
          disabled={disabled}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search detected fields, tables, clauses..."
          className="flex-1 py-3 text-sm outline-none placeholder:text-slate-400 disabled:opacity-50"
        />
      </div>

      <div className="max-h-80 overflow-y-auto p-2">
        {hasAnyDetected &&
          Array.from(grouped.entries()).map(([groupKey, groupTargetsList]) => (
            <section key={groupKey} className="mb-1">
              <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
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
                    className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-slate-50 disabled:opacity-50"
                  >
                    <span
                      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                        selected
                          ? "border-blue-600 bg-blue-600"
                          : "border-slate-300 bg-white"
                      }`}
                    >
                      {selected && <Check className="h-3 w-3 text-white" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-slate-800">
                        {target.label}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-slate-500">
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        {confidenceLabel(target)}
                      </span>
                    </span>
                  </button>
                );
              })}
            </section>
          ))}

        {!hasAnyDetected && (
          <p className="px-2 py-6 text-center text-sm text-slate-500">
            No structures were detected in this document yet.
          </p>
        )}

        {hasAnyDetected && filtered.length === 0 && (
          <p className="px-2 py-6 text-center text-sm text-slate-500">
            No detected items match &ldquo;{query}&rdquo;.
          </p>
        )}

        <section className="mt-1 border-t border-slate-100 pt-2">
          <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Custom
          </p>
          <div className="flex flex-wrap gap-2 px-2 pb-1">
            {customQuickPicks.map((pick) => (
              <button
                key={pick.key}
                type="button"
                disabled={disabled}
                onClick={() => onSelectCustom(pick)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-50"
              >
                {pick.label}
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 p-3">
        <button
          type="button"
          disabled={disabled || selectedIds.size === 0}
          onClick={onClear}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 transition hover:text-slate-700 disabled:opacity-40"
        >
          Clear
        </button>
        <div className="flex-1" />
        <button
          type="button"
          disabled={disabled || !hasAnyDetected}
          onClick={() => onSelectAll("field")}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-40"
        >
          Extract All Detected Fields
        </button>
        <button
          type="button"
          disabled={disabled || !hasAnyDetected}
          onClick={() => onSelectAll("table")}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-40"
        >
          Extract All Tables
        </button>
      </div>
    </div>
  );
}
