"use client";

import { useState } from "react";
import { Eye, LayoutGrid } from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import type { MetadataField } from "@/types/document";

interface MetadataGridProps {
  fields: MetadataField[];
}

const GROUP_ORDER = [
  "Identification",
  "Parties",
  "Dates",
  "Financial",
  "Legal",
  "Commercial",
  "Compliance",
];

export default function MetadataGrid({
  fields,
}: MetadataGridProps) {
  if (fields.length === 0) {
    return null;
  }

  const groups = new Map<string, MetadataField[]>();

  for (const field of fields) {
    const existing = groups.get(field.field_group) ?? [];
    existing.push(field);
    groups.set(field.field_group, existing);
  }

  const orderedGroups = [
    ...GROUP_ORDER.filter((group) => groups.has(group)),
    ...[...groups.keys()].filter(
      (group) => !GROUP_ORDER.includes(group),
    ),
  ];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <LayoutGrid className="h-4 w-4 text-blue-600" />

        <h2 className="text-sm font-semibold text-slate-950">
          Contract Metadata
        </h2>

        <span className="text-xs text-slate-400">
          {fields.length} field{fields.length === 1 ? "" : "s"}{" "}
          resolved
        </span>
      </div>

      <div className="mt-5 space-y-6">
        {orderedGroups.map((group) => (
          <div key={group}>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {group}
            </p>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {groups.get(group)!.map((field) => (
                <FieldTile key={field.field_key} field={field} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FieldTile({ field }: { field: MetadataField }) {
  const [showSource, setShowSource] = useState(false);

  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs text-slate-400">{field.label}</span>
        <ConfidenceBadge confidence={field.confidence} />
      </div>

      <p className="mt-1 break-words text-sm font-medium text-slate-800">
        {field.value}
      </p>

      <button
        type="button"
        onClick={() => setShowSource((value) => !value)}
        className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:text-blue-800"
      >
        <Eye className="h-3 w-3" />
        {showSource ? "Hide source" : "View source"}
      </button>

      {showSource && (
        <div className="mt-2 rounded-lg border border-slate-200 bg-white p-2 text-xs leading-5 text-slate-600">
          <p className="font-medium text-slate-800">
            {field.evidence.source_reference}
          </p>
          {field.evidence.section && (
            <p className="text-slate-500">
              {field.evidence.section}
            </p>
          )}
          <p className="mt-1 whitespace-pre-wrap">
            {field.evidence.source_text}
          </p>
        </div>
      )}
    </div>
  );
}
