"use client";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import QaBadge from "@/components/extraction/v3-qa-badge";
import type { V3ContractSummaryRow } from "@/lib/v3-export";

interface V3ContractSummaryPanelProps {
  summary: V3ContractSummaryRow;
  onOpenSource?: (request: SourceViewRequest) => void;
}

type SummaryKey = keyof V3ContractSummaryRow;

const GROUPS: { title: string; fields: [SummaryKey, string][] }[] = [
  {
    title: "Contract Identification",
    fields: [
      ["contract_number", "Contract Number"],
      ["solicitation_rfp", "Solicitation / RFP"],
      ["contract_vehicle", "Contract Vehicle"],
    ],
  },
  {
    title: "Parties",
    fields: [
      ["agency_office", "Agency / Office"],
      ["contractor", "Contractor"],
    ],
  },
  {
    title: "Dates & Duration",
    fields: [
      ["award_date", "Award Date"],
      ["base_period", "Base Period"],
      ["options", "Options"],
      ["max_duration", "Max Duration"],
    ],
  },
  {
    title: "Financial",
    fields: [
      ["ceiling_max_aggregate", "Ceiling / Max Aggregate"],
      ["minimum_guarantee", "Minimum Guarantee"],
    ],
  },
  {
    title: "Task Order / Classification",
    fields: [
      ["task_order_range", "Task Order Range"],
      ["naics", "NAICS"],
      ["size_standard", "Size Standard"],
    ],
  },
];

export default function V3ContractSummaryPanel({
  summary,
  onOpenSource,
}: V3ContractSummaryPanelProps) {
  const canOpenSource =
    Boolean(onOpenSource) &&
    typeof summary.source_page === "number" &&
    summary.source_page > 0;

  function openFieldSource(label: string, value: string) {
    if (!canOpenSource) return;
    onOpenSource?.({
      id: `contract_summary-${label}`,
      pageNumber: summary.source_page as number,
      highlightText: summary.evidence ?? null,
      label,
      value,
    });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {GROUPS.map((group) => (
          <div
            key={group.title}
            className="rounded-xl border border-border bg-surface p-4"
          >
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-secondary">
              {group.title}
            </h4>
            <dl className="space-y-2.5">
              {group.fields.map(([key, label]) => {
                const rawValue = summary[key];
                const value =
                  rawValue == null || rawValue === "" ? null : String(rawValue);
                const clickable = value != null && canOpenSource;
                return (
                  <div key={key}>
                    <dt className="text-xs text-text-secondary">{label}</dt>
                    {value == null ? (
                      <dd className="text-sm text-text-muted">Not found</dd>
                    ) : clickable ? (
                      <dd>
                        <button
                          type="button"
                          onClick={() => openFieldSource(label, value)}
                          className="text-left text-sm font-medium text-foreground underline decoration-dotted decoration-text-muted hover:text-primary hover:decoration-primary"
                          title="View source evidence"
                        >
                          {value}
                        </button>
                      </dd>
                    ) : (
                      <dd className="text-sm font-medium text-foreground">{value}</dd>
                    )}
                  </div>
                );
              })}
            </dl>
          </div>
        ))}

        <div className="rounded-xl border border-border bg-surface p-4">
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-secondary">
            Source / QA
          </h4>
          <dl className="space-y-2.5">
            <div>
              <dt className="text-xs text-text-secondary">Source File</dt>
              <dd className="text-sm font-medium text-foreground">
                {summary.source_file ?? <span className="text-text-muted">Not found</span>}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-text-secondary">Source Page</dt>
              <dd className="text-sm font-medium text-foreground">
                {summary.source_page ?? (
                  <span className="text-text-muted">Not found</span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-text-secondary">QA Status</dt>
              <dd>
                <QaBadge value={summary.qa_status} />
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
