"use client";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import StagingDatasetTable from "@/components/staging/staging-dataset-table";
import StagingFieldList from "@/components/staging/staging-field-list";
import { composePresentation, type PresentationGroup } from "@/lib/presentation-manifest";
import type { StagingWorkbook } from "@/lib/staging-workbook";
import { useState } from "react";

export default function PresentationWorkspace({
  workbook,
  documentId,
  onOpenSource,
}: {
  workbook: StagingWorkbook;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  const manifest = composePresentation(workbook);
  const [active, setActive] = useState(manifest.groups[0]?.id ?? "other");
  const current = manifest.groups.find((group) => group.id === active) ?? manifest.groups[0];

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-base font-semibold text-foreground">{manifest.heading}</h3>
        {manifest.subtitle && manifest.subtitle !== manifest.heading && (
          <p className="text-xs text-text-secondary">{manifest.subtitle}</p>
        )}
      </div>
      <div role="tablist" aria-label="Document sections" className="flex flex-wrap gap-1.5">
        {manifest.groups.map((group) => (
          <button
            key={group.id}
            type="button"
            role="tab"
            aria-label={group.label}
            aria-selected={current?.id === group.id}
            onClick={() => setActive(group.id)}
            className={[
              "rounded-md border px-2.5 py-1 text-[13px]",
              current?.id === group.id
                ? "border-primary bg-primary text-white"
                : "border-border bg-surface text-text-secondary",
            ].join(" ")}
          >
            {group.label}
          </button>
        ))}
      </div>
      {current ? (
        <GroupBody group={current} documentId={documentId} onOpenSource={onOpenSource} />
      ) : (
        <p className="text-sm text-text-secondary">
          No business fields were grouped for this document. Use Source to inspect the file.
        </p>
      )}
    </div>
  );
}

function GroupBody({
  group,
  documentId,
  onOpenSource,
}: {
  group: PresentationGroup;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  return (
    <div className="space-y-4">
      {group.datasets.map((dataset) => (
        <section key={dataset.dataset_id} className="space-y-2">
          {group.datasets.length > 1 && (
            <h4 className="text-sm font-medium text-foreground">{dataset.display_name}</h4>
          )}
          <p className="text-xs text-text-secondary">
            {(dataset.cardinality === "repeating" ? dataset.records.length : dataset.records.length).toLocaleString()}{" "}
            {dataset.cardinality === "repeating" ? "records" : "record"}
          </p>
          {dataset.cardinality === "single" ? (
            <StagingFieldList dataset={dataset} onOpenSource={onOpenSource} />
          ) : (
            <StagingDatasetTable dataset={dataset} documentId={documentId} onOpenSource={onOpenSource} dense />
          )}
        </section>
      ))}
    </div>
  );
}
