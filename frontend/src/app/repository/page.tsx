"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  GitBranch,
  List,
  Loader2,
  Plus,
  Search,
  Upload,
} from "lucide-react";

import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";
import { LoadingState } from "@/components/layout/StatusState";
import DocumentResultsTable from "@/components/document-results-table";
import ContractHierarchy from "@/components/contract-hierarchy";
import { getDocumentHierarchy, searchDocuments } from "@/lib/documents";
import {
  DOCUMENT_TYPE_OPTIONS,
  type DocumentStatus,
  type DocumentSummary,
  type HierarchyNode,
} from "@/types/document";

const PAGE_SIZE = 20;

type QuickFilter =
  | "all"
  | "active"
  | "needs_review"
  | "msa"
  | "amendment"
  | "sow";

const QUICK_FILTERS: { id: QuickFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "needs_review", label: "Needs Review" },
  { id: "msa", label: "MSA" },
  { id: "amendment", label: "Amendment" },
  { id: "sow", label: "SOW" },
];

type ViewMode = "table" | "hierarchy";

export default function RepositoryPage() {
  const [view, setView] = useState<ViewMode>("table");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [status, setStatus] = useState<DocumentStatus | "">("");
  const [documentType, setDocumentType] = useState("");
  const [confidenceMin, setConfidenceMin] = useState("");
  const [repositoryStatus, setRepositoryStatus] = useState("");
  const [hierarchyRoots, setHierarchyRoots] = useState<HierarchyNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (quickFilter === "all") {
      setStatus("");
      setDocumentType("");
      setRepositoryStatus("");
    } else if (quickFilter === "active") {
      setStatus("completed");
      setDocumentType("");
      setRepositoryStatus("");
    } else if (quickFilter === "needs_review") {
      setStatus("review_required");
      setDocumentType("");
      setRepositoryStatus("not_approved");
    } else if (quickFilter === "msa") {
      setDocumentType("Master Services Agreement");
      setStatus("");
      setRepositoryStatus("");
    } else if (quickFilter === "amendment") {
      setDocumentType("Amendment");
      setStatus("");
      setRepositoryStatus("");
    } else if (quickFilter === "sow") {
      setDocumentType("Statement of Work");
      setStatus("");
      setRepositoryStatus("");
    }
    setOffset(0);
  }, [quickFilter]);

  useEffect(() => {
    if (view !== "table") return;

    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result = await searchDocuments({
          q: query || undefined,
          status: status || undefined,
          documentType: documentType || undefined,
          repositoryStatus: repositoryStatus || undefined,
          limit: PAGE_SIZE,
          offset,
          ...(confidenceMin ? { confidence_min: Number(confidenceMin) } : {}),
        });

        if (!active) return;
        setDocuments(result.documents);
        setTotal(result.total);
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load the repository.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [
    view,
    query,
    status,
    documentType,
    confidenceMin,
    repositoryStatus,
    offset,
  ]);

  useEffect(() => {
    if (view !== "hierarchy") return;

    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result = await getDocumentHierarchy();
        if (active) setHierarchyRoots(result.roots);
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load the contract hierarchy.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [view]);

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <>
      <PageHero
        eyebrow="Store / Repository"
        title="Contract Repository"
        description="Search and analyze every agreement from one trusted source."
        actions={
          <>
            <Link href="/extraction/new" className="btn-hero-primary">
              <Plus className="h-4 w-4 shrink-0" />
              <span className="whitespace-nowrap">Add Contract</span>
            </Link>
            <button type="button" className="btn-hero-secondary">
              <Upload className="h-4 w-4 shrink-0" />
              <span className="whitespace-nowrap">Import</span>
            </button>
          </>
        }
      />

      <ContentSection>
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        {view === "table" && (
          <div className="relative min-w-[280px] flex-1 max-w-2xl">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
            <input
              type="text"
              value={query}
              onChange={(event) => {
                setOffset(0);
                setQuery(event.target.value);
              }}
              placeholder="Search contracts, counterparties, fields, or clauses..."
              className="w-full rounded-2xl border border-border bg-surface py-3.5 pl-11 pr-4 text-[15px] outline-none transition duration-200 focus:border-primary/30 focus:shadow-[var(--shadow-soft)]"
            />
          </div>
        )}

        <div className="flex items-center gap-1 rounded-full border border-border bg-surface p-1">
          <ViewToggle
            active={view === "table"}
            onClick={() => setView("table")}
            icon={List}
            label="Table"
          />
          <ViewToggle
            active={view === "hierarchy"}
            onClick={() => setView("hierarchy")}
            icon={GitBranch}
            label="Hierarchy"
          />
        </div>
      </div>

      {view === "table" && (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {QUICK_FILTERS.map((filter) => (
              <button
                key={filter.id}
                type="button"
                onClick={() => setQuickFilter(filter.id)}
                className={[
                  "chip",
                  quickFilter === filter.id ? "chip-active" : "",
                ].join(" ")}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setShowAdvanced((open) => !open)}
            className="mb-6 inline-flex items-center gap-1 text-sm text-text-secondary transition hover:text-foreground"
          >
            Filters
            <ChevronDown
              className={[
                "h-4 w-4 transition duration-200",
                showAdvanced ? "rotate-180" : "",
              ].join(" ")}
            />
          </button>

          {showAdvanced && (
            <div className="mb-8 flex flex-wrap gap-3">
              <AdvancedSelect
                label="Status"
                value={status}
                onChange={(value) => {
                  setOffset(0);
                  setStatus(value as DocumentStatus | "");
                }}
                options={[
                  { value: "", label: "All statuses" },
                  { value: "completed", label: "Completed" },
                  { value: "review_required", label: "Review required" },
                  { value: "processing", label: "Processing" },
                ]}
              />
              <AdvancedSelect
                label="Type"
                value={documentType}
                onChange={(value) => {
                  setOffset(0);
                  setDocumentType(value);
                }}
                options={[
                  { value: "", label: "All types" },
                  ...DOCUMENT_TYPE_OPTIONS.map((option) => ({
                    value: option,
                    label: option,
                  })),
                ]}
              />
              <AdvancedSelect
                label="Confidence"
                value={confidenceMin}
                onChange={(value) => {
                  setOffset(0);
                  setConfidenceMin(value);
                }}
                options={[
                  { value: "", label: "Any" },
                  { value: "0.95", label: "High (≥95%)" },
                  { value: "0.8", label: "Medium+ (≥80%)" },
                ]}
              />
            </div>
          )}
        </>
      )}

      {error && (
        <div className="mb-6 rounded-2xl border border-danger/20 bg-danger/5 p-4 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="editorial-card overflow-hidden">
        {loading ? (
          <LoadingState
            title="Indexing repository contracts..."
            description="Querying verified document metadata, family hierarchies, and extraction status."
          />
        ) : view === "table" ? (
          <DocumentResultsTable
            documents={documents}
            emptyMessage="No contracts match your filters."
            repositoryMode
          />
        ) : (
          <ContractHierarchy roots={hierarchyRoots} />
        )}
      </div>

      {view === "table" && total > 0 && (
        <div className="mt-8 flex items-center justify-between text-sm text-text-secondary">
          <p>
            Showing {from}–{to} of {total.toLocaleString()}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() =>
                setOffset((current) => Math.max(0, current - PAGE_SIZE))
              }
              disabled={offset === 0}
              className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => setOffset((current) => current + PAGE_SIZE)}
              disabled={offset + PAGE_SIZE >= total}
              className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
      </ContentSection>
    </>
  );
}

function ViewToggle({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-medium transition duration-200",
        active
          ? "bg-primary text-white"
          : "text-text-secondary hover:text-foreground",
      ].join(" ")}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

function AdvancedSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs text-text-secondary">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-xl border border-border bg-surface px-3 py-2 text-sm outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
