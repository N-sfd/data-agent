"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, Plus, Search, X } from "lucide-react";

import { ErrorState, LoadingState } from "@/components/layout/StatusState";
import { searchDocuments } from "@/lib/documents";
import {
  presentDocument,
  statusMark,
  type OperationalStatus,
} from "@/lib/document-presentation";
import type { DocumentStatus, DocumentSummary } from "@/types/document";

const PAGE_SIZE = 25;

type Filter = "all" | "review" | "ready" | "failed";

const FILTERS: { id: Filter; label: string; status?: DocumentStatus }[] = [
  { id: "all", label: "All Documents" },
  { id: "review", label: "Needs Review", status: "review_required" },
  { id: "ready", label: "Ready", status: "completed" },
  { id: "failed", label: "Failed", status: "failed" },
];

/** Document types reachable from the Documents menu (staging families). */
export const FAMILY_LABELS: Record<string, string> = {
  invoice: "Invoices",
  academic_transcript: "Transcripts & certificates",
  government_contract: "Contracts",
  far_regulation: "FAR regulations",
  correspondence: "Correspondence",
};

function isFilter(value: string | null): value is Filter {
  return FILTERS.some((item) => item.id === value);
}

const TONE: Record<OperationalStatus, string> = {
  ready: "text-success",
  verified: "text-success",
  review: "text-warning",
  failed: "text-danger",
  processing: "text-text-secondary",
};

export default function DocumentsHome() {
  const router = useRouter();
  const params = useSearchParams();
  const urlFilter = params.get("filter");
  const family = params.get("family") ?? "";
  const [filter, setFilter] = useState<Filter>(isFilter(urlFilter) ? urlFilter : "all");
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [debouncedQuery, setDebouncedQuery] = useState(query.trim());
  const [reloadKey, setReloadKey] = useState(0);
  const [offset, setOffset] = useState(0);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<Record<Filter, number> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      searchDocuments({ limit: 1, family: family || undefined }),
      searchDocuments({ status: "review_required", limit: 1, family: family || undefined }),
      searchDocuments({ status: "completed", limit: 1, family: family || undefined }),
      searchDocuments({ status: "failed", limit: 1, family: family || undefined }),
    ])
      .then(([all, review, ready, failed]) => {
        if (!active) return;
        setCounts({
          all: all.total,
          review: review.total,
          ready: ready.total,
          failed: failed.total,
        });
      })
      .catch(() => {
        /* The table error state covers a real outage. */
      });
    return () => {
      active = false;
    };
  }, [family]);

  // The Documents menu links here with ?filter= / ?family=; follow it.
  const [seenFilter, setSeenFilter] = useState(urlFilter);
  if (seenFilter !== urlFilter) {
    setSeenFilter(urlFilter);
    setFilter(isFilter(urlFilter) ? urlFilter : "all");
    setOffset(0);
  }

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let active = true;
    const status = FILTERS.find((item) => item.id === filter)?.status;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const result = await searchDocuments({
          q: debouncedQuery || undefined,
          status,
          family: family || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        if (!active) return;
        setDocuments(result.documents);
        setTotal(result.total);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to load documents.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [filter, debouncedQuery, offset, reloadKey, family]);

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            {family ? FAMILY_LABELS[family] ?? "Documents" : "Documents"}
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Every extracted document, with the staging profile Data Agent resolved.
          </p>
          {family && (
            <Link
              href="/documents"
              className="mt-2 inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary-soft px-2.5 py-0.5 text-xs font-medium text-primary hover:border-primary"
              aria-label={`Clear type filter ${FAMILY_LABELS[family] ?? family}`}
            >
              Type: {FAMILY_LABELS[family] ?? family}
              <X className="h-3 w-3" aria-hidden="true" />
            </Link>
          )}
        </div>
        <Link href="/extraction/new" className="btn-hero-primary">
          <Plus className="h-4 w-4" />
          New Document
        </Link>
      </div>

      <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <Metric label="Documents" value={counts?.all} />
        <Metric label="Need Review" value={counts?.review} tone="text-warning" />
        <Metric label="Ready" value={counts?.ready} tone="text-success" />
        <Metric label="Failed" value={counts?.failed} tone="text-danger" />
      </dl>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setOffset(0);
              setQuery(event.target.value);
            }}
            placeholder="Search documents, fields, parties, FAR numbers..."
            className="w-full rounded-xl border border-border bg-surface py-2.5 pl-9 pr-3 text-sm outline-none focus:border-primary/40"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={filter === item.id}
              onClick={() => {
                setOffset(0);
                setFilter(item.id);
              }}
              className={[
                "rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                filter === item.id
                  ? "border border-primary bg-primary text-white"
                  : "border border-border bg-surface text-text-secondary hover:border-primary/40 hover:text-foreground",
              ].join(" ")}
            >
              {item.label}
              <span className={filter === item.id ? "text-white/70" : "text-text-muted"}> {counts ? counts[item.id] : "–"}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mt-6">
          <ErrorState error={error} onRetry={() => setReloadKey((key) => key + 1)} />
        </div>
      )}

      <div className="mt-4 overflow-hidden rounded-xl border border-border bg-surface">
        {loading ? (
          <LoadingState title="Loading documents..." description="Connecting to Data Agent…" />
        ) : documents.length === 0 ? (
          <p className="px-6 py-12 text-center text-sm text-text-secondary">
            No documents match this view.
          </p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] font-medium text-text-muted">
                <th className="px-3 py-2">Document</th>
                <th className="px-3 py-2">Type</th>
                <th className="hidden px-3 py-2 sm:table-cell">Profile</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => {
                const row = presentDocument(document);
                return (
                  <tr
                    key={document.document_id}
                    onClick={() => router.push(`/documents/${document.document_id}`)}
                    className="h-11 cursor-pointer border-b border-border/70 last:border-0 hover:bg-surface-soft"
                  >
                    <td className="px-4 py-3 font-medium text-foreground">
                      {document.original_filename}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{row.typeLabel}</td>
                    <td className="hidden px-4 py-3 text-text-secondary sm:table-cell">
                      {row.profileLabel}
                    </td>
                    <td className={`px-4 py-3 font-medium ${TONE[row.status]}`}>
                      {statusMark(row.status)} {row.statusLabel}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-text-secondary">
          <p>
            {from}–{to} of {total.toLocaleString()}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
              className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <button
              type="button"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset((value) => value + PAGE_SIZE)}
              className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  tone = "text-foreground",
}: {
  label: string;
  value: number | undefined;
  tone?: string;
}) {
  return (
    <div>
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className={`text-lg font-semibold tabular-nums ${tone}`}>{value === undefined ? <span className="text-text-muted">—</span> : value.toLocaleString()}</dd>
    </div>
  );
}
