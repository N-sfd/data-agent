"use client";

import { useState } from "react";
import { Eye, LayoutGrid } from "lucide-react";

import ClickableFieldValue from "@/components/clickable-field-value";
import ConfidenceBadge from "@/components/confidence-badge";
import SourcePreviewDrawer, {
  type SourcePreviewRequest,
} from "@/components/source-preview-drawer";
import type { MetadataField } from "@/types/document";

interface MetadataGridProps {
  fields: MetadataField[];
  documentId: string;
  pageCount: number;
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
  documentId,
  pageCount,
}: MetadataGridProps) {
  const [sourceRequest, setSourceRequest] =
    useState<SourcePreviewRequest | null>(null);

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
    ...[...groups.keys()].filter((group) => !GROUP_ORDER.includes(group)),
  ];

  return (
    <div className="editorial-card p-6">
      <div className="flex items-center gap-2">
        <LayoutGrid className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-medium text-foreground">
          Contract Metadata
        </h2>
        <span className="text-xs text-text-secondary">
          {fields.length} field{fields.length === 1 ? "" : "s"} resolved
        </span>
      </div>

      <div className="mt-5 space-y-6">
        {orderedGroups.map((group) => (
          <div key={group}>
            <p className="text-xs font-medium uppercase tracking-wide text-text-secondary">
              {group}
            </p>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {groups.get(group)!.map((field) => (
                <FieldTile
                  key={field.field_key}
                  field={field}
                  onViewSource={() =>
                    setSourceRequest({
                      pageNumber: field.evidence.page_number,
                      highlightText: field.evidence.source_text,
                      label: field.label,
                    })
                  }
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      <SourcePreviewDrawer
        open={sourceRequest !== null}
        onClose={() => setSourceRequest(null)}
        documentId={documentId}
        pageCount={pageCount}
        request={sourceRequest}
      />
    </div>
  );
}

function FieldTile({
  field,
  onViewSource,
}: {
  field: MetadataField;
  onViewSource: () => void;
}) {
  const [showSource, setShowSource] = useState(false);

  return (
    <div className="rounded-xl bg-surface-soft p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs text-text-secondary">{field.label}</span>
        <ConfidenceBadge confidence={field.confidence} />
      </div>

      <div className="mt-1">
        <ClickableFieldValue
          fieldKey={field.field_key}
          fieldLabel={field.label}
          value={field.value}
        />
      </div>

      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={() => setShowSource((value) => !value)}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          <Eye className="h-3 w-3" />
          {showSource ? "Hide source" : "View source"}
        </button>

        <button
          type="button"
          onClick={onViewSource}
          className="text-xs font-medium text-text-secondary hover:text-primary hover:underline"
        >
          View page
        </button>
      </div>

      {showSource && (
        <div className="mt-2 rounded-lg border border-border bg-surface p-2 text-xs leading-5 text-text-secondary">
          <p className="font-medium text-foreground">
            {field.evidence.source_reference}
          </p>
          {field.evidence.section && (
            <p className="text-text-muted">{field.evidence.section}</p>
          )}
          <p className="mt-1 whitespace-pre-wrap">
            {field.evidence.source_text}
          </p>
        </div>
      )}
    </div>
  );
}
