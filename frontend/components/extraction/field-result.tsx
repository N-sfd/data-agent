"use client";

import { useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, Eye, Sparkles } from "lucide-react";

import type { UniversalValue } from "@/types/document";

interface FieldResultProps {
  values: UniversalValue[];
}

function methodLabel(method: string): string {
  switch (method) {
    case "form_field":
      return "PDF Form Field";
    case "label_value":
      return "Label / Value";
    case "regex":
      return "Pattern Match";
    case "table":
      return "Table";
    case "ai":
      return "AI Fallback";
    default:
      return method;
  }
}

interface ValueGroup {
  label: string;
  value: unknown;
  items: UniversalValue[];
}

// Collapse repeated hits for the same label/value (e.g. a contract
// number that appears on pages 53, 64, and 69) into one canonical
// entry instead of one per occurrence — source evidence is kept, not
// discarded.
function groupValues(values: UniversalValue[]): ValueGroup[] {
  const groups = new Map<string, ValueGroup>();

  for (const item of values) {
    const key = `${item.label}::${String(item.value ?? "")}`;
    const existing = groups.get(key);

    if (existing) {
      existing.items.push(item);
    } else {
      groups.set(key, { label: item.label, value: item.value, items: [item] });
    }
  }

  return Array.from(groups.values());
}

function MethodBadge({ isAi }: { isAi: boolean }) {
  return isAi ? (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-violet-50 px-2.5 py-1 text-xs font-semibold text-violet-700">
      <Sparkles className="h-3.5 w-3.5" />
      AI-assisted
    </span>
  ) : (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
      <CheckCircle2 className="h-3.5 w-3.5" />
      Deterministic
    </span>
  );
}

function SourceList({ items }: { items: UniversalValue[] }) {
  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div
          key={index}
          className="rounded-lg border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-600"
        >
          <p className="font-medium text-slate-800">
            {item.evidence.source_reference}
          </p>
          <p className="mt-2 whitespace-pre-wrap">
            {item.evidence.source_text}
          </p>
        </div>
      ))}
    </div>
  );
}

function ValueCard({ group }: { group: ValueGroup }) {
  const [showSources, setShowSources] = useState(false);

  const first = group.items[0];
  const isAi = first.extraction_method === "ai";
  const anyVerified = group.items.some((item) => item.verified);
  const pages = Array.from(
    new Set(group.items.map((item) => item.evidence.page_number)),
  ).sort((a, b) => a - b);

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {group.label}
          </p>
          <p className="mt-1 text-lg font-semibold text-slate-950">
            {String(group.value ?? "")}
          </p>
        </div>

        <MethodBadge isAi={isAi} />
      </div>

      <p className="mt-3 text-xs text-slate-500">
        {pages.length > 1
          ? `Found on ${pages.length} pages · Pages ${pages.join(", ")}`
          : `Page ${pages[0]} · ${methodLabel(first.extraction_method)}`}
        {anyVerified && " · Source verified"}
      </p>

      <button
        type="button"
        onClick={() => setShowSources((value) => !value)}
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700 hover:text-blue-800"
      >
        <Eye className="h-3.5 w-3.5" />
        {showSources
          ? "Hide Source"
          : pages.length > 1
            ? "View Sources"
            : "View Source"}
      </button>

      {showSources && (
        <div className="mt-3">
          <SourceList items={group.items} />
        </div>
      )}
    </div>
  );
}

function ValueRow({ group }: { group: ValueGroup }) {
  const [expanded, setExpanded] = useState(false);

  const first = group.items[0];
  const isAi = first.extraction_method === "ai";
  const anyVerified = group.items.some((item) => item.verified);
  const pages = Array.from(
    new Set(group.items.map((item) => item.evidence.page_number)),
  ).sort((a, b) => a - b);

  return (
    <>
      <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
        <td className="px-4 py-3 align-top">
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="flex items-start gap-1.5 text-left"
          >
            {expanded ? (
              <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
            ) : (
              <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
            )}
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {group.label}
            </span>
          </button>
        </td>
        <td className="px-4 py-3 align-top text-sm font-medium text-slate-900">
          {String(group.value ?? "")}
        </td>
        <td className="whitespace-nowrap px-4 py-3 align-top text-xs text-slate-500">
          {pages.length > 1 ? `${pages.length} pages` : `Page ${pages[0]}`}
          {anyVerified && (
            <span className="ml-1 inline-flex items-center gap-0.5 text-emerald-600">
              <CheckCircle2 className="h-3 w-3" />
            </span>
          )}
        </td>
        <td className="whitespace-nowrap px-4 py-3 align-top">
          <MethodBadge isAi={isAi} />
        </td>
      </tr>

      {expanded && (
        <tr className="border-b border-slate-100 bg-slate-50/60 last:border-0">
          <td colSpan={4} className="px-4 py-3">
            <SourceList items={group.items} />
          </td>
        </tr>
      )}
    </>
  );
}

// Spacious cards read best for a handful of standout fields; once
// there are several results (contacts, line-level fields, etc.) a
// compact table keeps the page from turning into a wall of cards.
const COMPACT_TABLE_THRESHOLD = 4;

export default function FieldResult({ values }: FieldResultProps) {
  const groups = groupValues(values);

  if (groups.length === 0) {
    return null;
  }

  if (groups.length < COMPACT_TABLE_THRESHOLD) {
    return (
      <div className="space-y-3">
        {groups.map((group, index) => (
          <ValueCard key={`${group.label}-${index}`} group={group} />
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="whitespace-nowrap border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700">
              Field
            </th>
            <th className="whitespace-nowrap border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700">
              Value
            </th>
            <th className="whitespace-nowrap border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700">
              Source
            </th>
            <th className="whitespace-nowrap border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700">
              Method
            </th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group, index) => (
            <ValueRow key={`${group.label}-${index}`} group={group} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
