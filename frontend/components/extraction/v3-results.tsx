"use client";

import { ChevronDown, Download } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import V3ContractSummaryPanel from "@/components/extraction/v3-contract-summary-panel";
import V3DatasetTable from "@/components/extraction/v3-dataset-table";
import { isNeedsReview } from "@/components/extraction/v3-qa-badge";
import { ApiError } from "@/lib/api";
import {
  downloadV3DatasetCsv,
  downloadV3ExportXlsx,
  getNormalizedV3Document,
  type NormalizedV3Document,
} from "@/lib/v3-export";

interface V3ResultsProps {
  documentId: string;
  documentName?: string;
  onOpenSource?: (request: SourceViewRequest) => void;
  /** Changes whenever the underlying extraction result changes (e.g. a new
   * job completed for this same documentId in the same page session).
   * V3 data is produced by that same job, so a stale fetch from an earlier
   * job/partial state must be refetched — this component has no other
   * signal that the job re-ran, since `documentId` alone doesn't change. */
  refreshKey?: string | number;
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

// Per-dataset (label, value) column keys used to build the source-
// verification request when a row is clicked — the two most identifying
// columns of that dataset, not every column.
const IDENTITY_COLUMNS: Record<V3TabId, [string, string]> = {
  contract_summary: ["contract_number", "contractor"],
  clins: ["clin", "description"],
  funding: ["funding_level", "funding_status"],
  performance_delivery: ["record_type", "requirement"],
  attachments: ["attachment_reference", "title_description"],
  clauses: ["clause_number", "clause_title"],
  far_references: ["far_reference", "subject_context"],
  dfars: ["clause_number", "clause_title"],
  all_fields: ["normalized_field", "value"],
  qa_review: ["qa_check", "details"],
  source_documents: ["source_document", "role"],
};

// column key -> display header, per dataset. Mirrors
// backend/app/services/v3_export_builder.py's header lists exactly.
const COLUMNS: Record<V3TabId, [string, string][]> = {
  contract_summary: [],
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

// Export menu is deliberately a fixed, explicit list (not "every dataset")
// per the accepted checkpoint spec — QA Review / Source Documents are
// reviewed in-app, not exported standalone.
const CSV_EXPORTS: { dataset: string; label: string }[] = [
  { dataset: "all-fields", label: "All Fields CSV" },
  { dataset: "clins", label: "CLINs CSV" },
  { dataset: "funding", label: "Funding CSV" },
  { dataset: "performance-delivery", label: "Performance Delivery CSV" },
  { dataset: "attachments", label: "Attachments CSV" },
  { dataset: "clauses", label: "Clauses CSV" },
  { dataset: "far-references", label: "FAR References CSV" },
  { dataset: "dfars", label: "DFARS CSV" },
  { dataset: "contract-summary", label: "Contract Summary CSV" },
];

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

// QA Review's own `qa_check` values (see backend/app/services/
// qa_review_builder.py) map onto the dataset tab they describe, so a
// reviewer can jump straight from a flagged rollup row to the records it's
// about.
const QA_CHECK_TO_TAB: Record<string, V3TabId> = {
  "Contract Summary": "contract_summary",
  CLINs: "clins",
  Funding: "funding",
  "Performance / Delivery": "performance_delivery",
  Attachments: "attachments",
  Clauses: "clauses",
  "FAR References": "far_references",
  DFARS: "dfars",
  "All Fields": "all_fields",
};

const SUMMARY_STRIP: { tab: V3TabId; label: string }[] = [
  { tab: "contract_summary", label: "Contract Summary" },
  { tab: "clins", label: "CLINs" },
  { tab: "funding", label: "Funding" },
  { tab: "performance_delivery", label: "Performance" },
  { tab: "attachments", label: "Attachments" },
  { tab: "clauses", label: "Clauses" },
  { tab: "far_references", label: "FAR References" },
  { tab: "dfars", label: "DFARS" },
];

// Datasets whose rows carry a per-record qa_status — used both to total
// "Needs Review" in the summary strip and to decide whether a dataset
// table should offer the Verified/Needs Review filter at all.
const QA_STATUS_DATASETS: V3TabId[] = [
  "clins",
  "funding",
  "performance_delivery",
  "attachments",
  "clauses",
  "far_references",
  "dfars",
  "all_fields",
];

export default function V3Results({
  documentId,
  documentName,
  onOpenSource,
  refreshKey,
}: V3ResultsProps) {
  const [doc, setDoc] = useState<NormalizedV3Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [activeTab, setActiveTab] = useState<V3TabId>("contract_summary");
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    // The V3 persistence stage runs AFTER the legacy extraction batches
    // finish (last stage in the same job, ~3-10s of its own), so a fetch
    // triggered right when that job completes can land before V3 data
    // actually exists yet — not a genuinely-empty document, just a fetch
    // that raced the job's own last stage. A totally empty document is
    // implausible (even a sparse contract has SOME All Fields/Contract
    // Summary data), so retry a few times with a delay rather than
    // showing a false "no data" state.
    const RETRY_DELAYS_MS = [2500, 4000, 6000];

    function isEmpty(data: NormalizedV3Document): boolean {
      return (
        data.all_fields.length === 0 &&
        data.clins.length === 0 &&
        data.clauses.length === 0 &&
        data.attachments.length === 0 &&
        !data.contract_summary
      );
    }

    async function load() {
      setLoading(true);
      setError(null);
      setAuthRequired(false);
      for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt += 1) {
        try {
          const data = await getNormalizedV3Document(documentId);
          if (cancelled) return;
          if (!isEmpty(data) || attempt === RETRY_DELAYS_MS.length) {
            setDoc(data);
            setLoading(false);
            return;
          }
        } catch (err) {
          if (cancelled) return;
          // The V3 endpoint requires documents.view. Retrying can't fix a
          // missing/insufficient credential, so say what's needed right away.
          if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
            setError(
              err.status === 401
                ? "Sign-in required to view V3 canonical results."
                : "Your access key doesn't have permission to view V3 canonical results.",
            );
            setAuthRequired(true);
            setLoading(false);
            return;
          }
          if (attempt === RETRY_DELAYS_MS.length) {
            // Real backend failures (404/500/network) should never leak
            // raw status text into the UI — the Retry action is the
            // recovery path, and the actual error is still visible in
            // devtools/network.
            setError("Unable to load V3 canonical results.");
            setLoading(false);
            return;
          }
        }
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[attempt]));
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [documentId, refreshKey, retryTick]);

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

  const needsReviewTotal = useMemo(() => {
    if (!doc) return 0;
    let total = 0;
    for (const tab of QA_STATUS_DATASETS) {
      for (const row of rowsFor(doc, tab)) {
        if (isNeedsReview(row["qa_status"])) total += 1;
      }
    }
    if (doc.contract_summary && isNeedsReview(doc.contract_summary.qa_status)) {
      total += 1;
    }
    return total;
  }, [doc]);

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-surface-soft p-6 text-sm text-text-secondary">
        Preparing canonical V3 results...
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="space-y-3 rounded-xl border border-border bg-surface-soft p-6 text-sm">
        <p className="text-danger">
          {error ?? "Unable to load V3 canonical results."}
        </p>
        {authRequired ? (
          <p className="text-text-secondary">
            Add a service API key on the{" "}
            <Link href="/api-keys" className="font-medium underline">
              API keys
            </Link>{" "}
            page, then retry.
          </p>
        ) : null}
        <button
          type="button"
          onClick={() => setRetryTick((tick) => tick + 1)}
          className="btn-secondary text-xs"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-foreground">
            V3 Canonical Extraction
          </h3>
          <p className="text-xs text-text-secondary">
            {documentName ?? doc.document_filename} — structure-classified,
            source-grounded datasets — the canonical business export for this
            contract.
          </p>
        </div>
        <div className="relative" ref={exportMenuRef}>
          <button
            type="button"
            onClick={() => setExportMenuOpen((open) => !open)}
            className="btn-primary text-sm"
          >
            <Download className="h-4 w-4" />
            Export
            <ChevronDown className="h-4 w-4" />
          </button>
          {exportMenuOpen && (
            <div className="absolute right-0 top-full z-10 mt-1 w-64 rounded-lg border border-border bg-surface p-1 shadow-lg">
              <button
                type="button"
                onClick={() => {
                  downloadV3ExportXlsx(documentId, `${doc.document_filename}_V3`);
                  setExportMenuOpen(false);
                }}
                className="block w-full rounded-md px-3 py-2 text-left text-xs font-semibold text-foreground hover:bg-surface-soft"
              >
                Complete V3 Excel
              </button>
              <div className="my-1 border-t border-border" />
              {CSV_EXPORTS.map((item) => (
                <button
                  key={item.dataset}
                  type="button"
                  onClick={() => {
                    downloadV3DatasetCsv(documentId, item.dataset);
                    setExportMenuOpen(false);
                  }}
                  className="block w-full rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-surface-soft"
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 rounded-xl border border-border bg-surface p-4 sm:grid-cols-4 lg:grid-cols-9">
        {SUMMARY_STRIP.map((item) => (
          <button
            key={item.tab}
            type="button"
            onClick={() => setActiveTab(item.tab)}
            className="text-left"
          >
            <p className="text-lg font-medium tabular-nums text-foreground">
              {item.tab === "contract_summary"
                ? doc.contract_summary
                  ? "Available"
                  : "Not found"
                : (tabCounts[item.tab] ?? 0)}
            </p>
            <p className="mt-0.5 text-xs text-text-secondary">{item.label}</p>
          </button>
        ))}
        <button
          type="button"
          onClick={() => setActiveTab("qa_review")}
          className="text-left"
        >
          <p
            className={`text-lg font-medium tabular-nums ${needsReviewTotal > 0 ? "text-warning" : "text-foreground"}`}
          >
            {needsReviewTotal}
          </p>
          <p className="mt-0.5 text-xs text-text-secondary">Needs Review</p>
        </button>
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
              ({tab.id === "contract_summary"
                ? doc.contract_summary
                  ? 1
                  : 0
                : (tabCounts[tab.id] ?? 0)})
            </span>
          </button>
        ))}
      </div>

      {activeTab === "contract_summary" ? (
        doc.contract_summary ? (
          <V3ContractSummaryPanel
            summary={doc.contract_summary}
            onOpenSource={onOpenSource}
          />
        ) : (
          <div className="rounded-xl border border-border bg-surface-soft px-4 py-10 text-center text-sm text-text-secondary">
            No source-supported records found.
          </div>
        )
      ) : activeTab === "qa_review" ? (
        <div className="space-y-2 rounded-xl border border-border">
          <table className="w-full min-w-max divide-y divide-border text-sm">
            <thead className="bg-surface-soft">
              <tr>
                {COLUMNS.qa_review.map(([key, label]) => (
                  <th
                    key={key}
                    className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary"
                  >
                    {label}
                  </th>
                ))}
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rowsFor(doc, "qa_review").length === 0 ? (
                <tr>
                  <td
                    colSpan={COLUMNS.qa_review.length + 1}
                    className="px-3 py-8 text-center text-sm text-text-muted"
                  >
                    No source-supported records found.
                  </td>
                </tr>
              ) : (
                rowsFor(doc, "qa_review").map((row, index) => {
                  const targetTab = QA_CHECK_TO_TAB[String(row["qa_check"] ?? "")];
                  return (
                    <tr key={index} className="align-top">
                      {COLUMNS.qa_review.map(([key]) => (
                        <td
                          key={key}
                          className="max-w-sm px-3 py-2 text-foreground"
                        >
                          {key === "result" ? (
                            <span
                              className={
                                String(row[key] ?? "").toUpperCase().startsWith("PASS")
                                  ? "font-medium text-success"
                                  : "font-medium text-warning"
                              }
                            >
                              {String(row[key] ?? "")}
                            </span>
                          ) : (
                            String(row[key] ?? "")
                          )}
                        </td>
                      ))}
                      <td className="px-3 py-2 text-right">
                        {targetTab && (
                          <button
                            type="button"
                            onClick={() => setActiveTab(targetTab)}
                            className="text-xs font-medium text-primary hover:underline"
                          >
                            View dataset →
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <V3DatasetTable
          datasetId={activeTab}
          columns={COLUMNS[activeTab]}
          rows={rowsFor(doc, activeTab)}
          qaStatusKey={QA_STATUS_DATASETS.includes(activeTab) ? "qa_status" : null}
          identityColumns={IDENTITY_COLUMNS[activeTab]}
          onOpenSource={onOpenSource}
        />
      )}
    </div>
  );
}
