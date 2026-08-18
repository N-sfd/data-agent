"use client";

import { useEffect, useState } from "react";
import { Archive, ChevronLeft, ChevronRight, Search } from "lucide-react";

import DocumentResultsTable from "@/components/document-results-table";
import { searchDocuments } from "@/lib/documents";
import type { DocumentStatus, DocumentSummary } from "@/types/document";

const PAGE_SIZE = 20;

const STATUS_OPTIONS: { value: DocumentStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "completed", label: "Completed" },
  { value: "review_required", label: "Review Required" },
  { value: "processing", label: "Processing" },
];

export default function RepositoryPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<DocumentStatus | "">("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result = await searchDocuments({
          q: query || undefined,
          status: status || undefined,
          limit: PAGE_SIZE,
          offset,
        });

        if (!active) return;

        setDocuments(result.documents);
        setTotal(result.total);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load the repository.",
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    load();

    return () => {
      active = false;
    };
  }, [query, status, offset]);

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8 flex items-center gap-2">
        <Archive className="h-5 w-5 text-blue-600" />
        <div>
          <p className="text-sm font-semibold text-blue-600">
            Contract Extraction
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">
            Repository
          </h1>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(event) => {
              setOffset(0);
              setQuery(event.target.value);
            }}
            placeholder="Search by filename or contract number..."
            className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-800"
          />
        </div>

        <select
          value={status}
          onChange={(event) => {
            setOffset(0);
            setStatus(event.target.value as DocumentStatus | "");
          }}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading && documents.length === 0 ? (
          <p className="p-10 text-center text-sm text-slate-500">
            Loading...
          </p>
        ) : (
          <DocumentResultsTable
            documents={documents}
            emptyMessage="No documents match your filters."
          />
        )}
      </div>

      {total > 0 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
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
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>

            <button
              type="button"
              onClick={() =>
                setOffset((current) => current + PAGE_SIZE)
              }
              disabled={offset + PAGE_SIZE >= total}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
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
