"use client";

import { ChevronDown, Download } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  downloadV3DatasetCsv,
  downloadV3ExportXlsx,
  getNormalizedV3Document,
  type NormalizedV3Document,
} from "@/lib/v3-export";

interface V3ResultsProps {
  documentId: string;
  documentName?: string;
}

type V3TabId =
  | "contract_summary"
  | "clins"
  | "funding"
  | "performance_delivery"
  | "attachments"
  | "clauses"
  | "far_references"
  | "dfars"
  | "all_fields"
  | "qa_review"
  | "source_documents";

const TABS: { id: V3TabId; label: string; dataset: string }[] = [
  { id: "contract_summary", label: "Contract Summary", dataset: "contract-summary" },
  { id: "clins", label: "CLINs", dataset: "clins" },
  { id: "funding", label: "Funding", dataset: "funding" },
  { id: "performance_delivery", label: "Performance Delivery", dataset: "performance-delivery" },
  { id: "attachments", label: "Attachments", dataset: "attachments" },
  { id: "clauses", label: "Clauses", dataset: "clauses" },
  { id: "far_references", label: "FAR References", dataset: "far-references" },
  { id: "dfars", label: "DFARS", dataset: "dfars" },
  { id: "all_fields", label: "All Fields", dataset: "all-fields" },
  { id: "qa_review", label: "QA Review", dataset: "qa-review" },
  { id: "source_documents", label: "Source Documents", dataset: "source-documents" },
];

// column key -> display header, per dataset. Mirrors
// backend/app/services/v3_export_builder.py's header lists exactly.
const COLUMNS: Record<V3TabId, [string, string][]> = {
  contract_summary: [
    ["contract_number", "Contract Number"],
    ["solicitation_rfp", "Solicitation / RFP"],
    ["contract_vehicle", "Contract Vehicle"],
    ["agency_office", "Agency / Office"],
    ["contractor", "Contractor"],
    ["award_date", "Award Date"],
    ["ceiling_max_aggregate", "Ceiling / Max Aggregate"],
    ["minimum_guarantee", "Minimum Guarantee"],
    ["base_period", "Base Period"],
    ["options", "Options"],
    ["max_duration", "Max Duration"],
    ["task_order_range", "Task Order Range"],
    ["naics", "NAICS"],
    ["size_standard", "Size Standard"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["qa_status", "QA Status"],
  ],
  clins: [
    ["clin", "CLIN"],
    ["option_base", "Option/Base"],
    ["description", "Description"],
    ["pricing_type", "Pricing Type"],
    ["max_quantity", "Max Quantity"],
    ["unit", "Unit"],
    ["unit_price", "Unit Price"],
    ["max_amount", "Max Amount"],
    ["status", "Status"],
    ["fob", "FOB"],
    ["purchase_request", "Purchase Request"],
    ["psc", "PSC"],
    ["pop_start", "POP Start"],
    ["pop_end", "POP End"],
    ["ship_to", "Ship To"],
    ["dodaac", "DODAAC"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["qa_status", "QA Status"],
  ],
  funding: [
    ["funding_level", "Funding Level"],
    ["clin", "CLIN"],
    ["funding_status", "Funding Status"],
    ["amount", "Amount"],
    ["accounting_appropriation", "Accounting / Appropriation"],
    ["purchase_request", "Purchase Request"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["qa_status", "QA Status"],
  ],
  performance_delivery: [
    ["record_type", "Record Type"],
    ["clin", "CLIN"],
    ["start", "Start"],
    ["end_timing", "End / Timing"],
    ["location_destination", "Location / Destination"],
    ["requirement", "Requirement"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["qa_status", "QA Status"],
  ],
  attachments: [
    ["attachment_reference", "Attachment / Reference"],
    ["title_description", "Title / Description"],
    ["included_in_portfolio", "Included in Portfolio?"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["qa_status", "QA Status"],
  ],
  clauses: [
    ["regulation", "Regulation"],
    ["clause_number", "Clause Number"],
    ["clause_title", "Clause Title"],
    ["alternate_deviation", "Alternate / Deviation"],
    ["effective_date", "Effective Date"],
    ["incorporation_type", "Incorporation Type"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["qa_status", "QA Status"],
  ],
  far_references: [
    ["far_reference", "FAR Reference"],
    ["reference_type", "Reference Type"],
    ["subject_context", "Subject / Context"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["contract_clause", "Contract Clause?"],
    ["qa_status", "QA Status"],
  ],
  dfars: [
    ["regulation", "Regulation"],
    ["clause_number", "Clause Number"],
    ["clause_title", "Clause Title"],
    ["alternate_deviation", "Alternate / Deviation"],
    ["effective_date", "Effective Date"],
    ["incorporation_type", "Incorporation Type"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["qa_status", "QA Status"],
  ],
  all_fields: [
    ["category", "Category"],
    ["normalized_field", "Normalized Field"],
    ["value", "Value"],
    ["source_file", "Source File"],
    ["source_page", "Source Page"],
    ["evidence", "Evidence"],
    ["extraction_method", "Extraction Method"],
    ["qa_status", "QA Status"],
  ],
  qa_review: [
    ["qa_check", "QA Check"],
    ["result", "Result"],
    ["details", "Details"],
    ["action", "Action"],
  ],
  source_documents: [
    ["source_document", "Source Document"],
    ["role", "Role"],
    ["pages", "Pages"],
    ["extraction_status", "Extraction Status"],
  ],
};

function rowsFor(doc: NormalizedV3Document, tab: V3TabId): Record<string, unknown>[] {
  switch (tab) {
    case "contract_summary":
      return doc.contract_summary ? [doc.contract_summary as unknown as Record<string, unknown>] : [];
    case "clins":
      return doc.clins as unknown as Record<string, unknown>[];
    case "funding":
      return doc.funding as unknown as Record<string, unknown>[];
    case "performance_delivery":
      return doc.performance_delivery as unknown as Record<string, unknown>[];
    case "attachments":
      return doc.attachments as unknown as Record<string, unknown>[];
    case "clauses":
      return doc.clauses as unknown as Record<string, unknown>[];
    case "far_references":
      return doc.far_references as unknown as Record<string, unknown>[];
    case "dfars":
      return doc.dfars as unknown as Record<string, unknown>[];
    case "all_fields":
      return doc.all_fields as unknown as Record<string, unknown>[];
    case "qa_review":
      return doc.qa_review as unknown as Record<string, unknown>[];
    case "source_documents":
      return doc.source_documents as unknown as Record<string, unknown>[];
    default:
      return [];
  }
}

function QaBadge({ value }: { value: unknown }) {
  const text = value == null ? "" : String(value);
  const lowered = text.toLowerCase();
  const tone = lowered.includes("verified") || lowered.includes("pass")
    ? "bg-success/15 text-success"
    : lowered.includes("review")
      ? "bg-warning/15 text-warning"
      : "bg-surface-soft text-text-secondary";
  if (!text) return null;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>
      {text}
    </span>
  );
}

export default function V3Results({ documentId, documentName }: V3ResultsProps) {
  const [doc, setDoc] = useState<NormalizedV3Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<V3TabId>("contract_summary");
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getNormalizedV3Document(documentId)
      .then((data) => {
        if (!cancelled) setDoc(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load V3 results.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        exportMenuRef.current &&
        !exportMenuRef.current.contains(event.target as Node)
      ) {
        setExportMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const tabCounts = useMemo(() => {
    if (!doc) return {} as Record<V3TabId, number>;
    const counts = {} as Record<V3TabId, number>;
    for (const tab of TABS) {
      counts[tab.id] = rowsFor(doc, tab.id).length;
    }
    return counts;
  }, [doc]);

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-surface-soft p-6 text-sm text-text-secondary">
        Loading V3 canonical results...
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="rounded-xl border border-border bg-surface-soft p-6 text-sm text-danger">
        {error ?? "V3 results are not available for this document yet."}
      </div>
    );
  }

  const activeColumns = COLUMNS[activeTab];
  const activeRows = rowsFor(doc, activeTab);
  const activeDataset = TABS.find((tab) => tab.id === activeTab)?.dataset ?? "all-fields";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            V3 Canonical Extraction — {documentName ?? doc.document_filename}
          </h3>
          <p className="text-xs text-text-secondary">
            Structure-classified, source-grounded datasets — the canonical
            business export for this contract.
          </p>
        </div>
        <div className="relative" ref={exportMenuRef}>
          <button
            type="button"
            onClick={() => setExportMenuOpen((open) => !open)}
            className="btn-primary text-sm"
          >
            <Download className="h-4 w-4" />
            Export V3
            <ChevronDown className="h-4 w-4" />
          </button>
          {exportMenuOpen && (
            <div className="absolute right-0 top-full z-10 mt-1 w-64 rounded-lg border border-border bg-surface p-1 shadow-lg">
              <button
                type="button"
                onClick={() => {
                  downloadV3DatasetCsv(documentId, activeDataset);
                  setExportMenuOpen(false);
                }}
                className="block w-full rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-surface-soft"
              >
                {TABS.find((tab) => tab.id === activeTab)?.label} CSV
              </button>
              <button
                type="button"
                onClick={() => {
                  downloadV3ExportXlsx(documentId, `${doc.document_filename}_V3`);
                  setExportMenuOpen(false);
                }}
                className="block w-full rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-surface-soft"
              >
                Complete Excel (all 12 sheets)
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-border pb-px">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={[
              "whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition",
              activeTab === tab.id
                ? "border-success text-foreground"
                : "border-transparent text-text-secondary hover:text-foreground",
            ].join(" ")}
          >
            {tab.label}
            <span className="ml-1.5 text-xs text-text-muted">
              ({tabCounts[tab.id] ?? 0})
            </span>
          </button>
        ))}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-surface-soft">
            <tr>
              {activeColumns.map(([key, label]) => (
                <th
                  key={key}
                  className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {activeRows.length === 0 ? (
              <tr>
                <td
                  colSpan={activeColumns.length}
                  className="px-3 py-6 text-center text-sm text-text-muted"
                >
                  No records for this dataset.
                </td>
              </tr>
            ) : (
              activeRows.map((row, index) => (
                <tr key={index} className="hover:bg-surface-soft/60">
                  {activeColumns.map(([key]) => (
                    <td
                      key={key}
                      className="max-w-xs truncate whitespace-nowrap px-3 py-2 text-foreground"
                      title={row[key] == null ? "" : String(row[key])}
                    >
                      {key === "qa_status" ? (
                        <QaBadge value={row[key]} />
                      ) : row[key] == null ? (
                        <span className="text-text-muted">—</span>
                      ) : (
                        String(row[key])
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
