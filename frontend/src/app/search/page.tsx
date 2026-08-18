"use client";

import { useEffect, useState } from "react";
import { Search as SearchIcon } from "lucide-react";

import DocumentResultsTable from "@/components/document-results-table";
import { searchDocuments } from "@/lib/documents";
import type { DocumentSummary } from "@/types/document";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!submittedQuery) {
      return;
    }

    let active = true;

    async function run() {
      setLoading(true);
      setError("");

      try {
        const result = await searchDocuments({
          q: submittedQuery,
          limit: 50,
        });

        if (!active) return;

        setDocuments(result.documents);
        setTotal(result.total);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error ? err.message : "Search failed.",
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    run();

    return () => {
      active = false;
    };
  }, [submittedQuery]);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    const trimmed = query.trim();
    setSubmittedQuery(trimmed);

    if (!trimmed) {
      setDocuments([]);
      setTotal(0);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-8 flex items-center gap-2">
        <SearchIcon className="h-5 w-5 text-blue-600" />
        <div>
          <p className="text-sm font-semibold text-blue-600">
            Contract Extraction
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">
            Search
          </h1>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search filenames, contract numbers, or contract text..."
            autoFocus
            className="w-full rounded-2xl border border-slate-300 py-3 pl-11 pr-4 text-sm text-slate-800 shadow-sm"
          />
        </div>
      </form>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <p className="text-sm text-slate-500">Searching...</p>
      )}

      {!loading && submittedQuery && (
        <p className="mb-3 text-xs text-slate-500">
          {total} result{total === 1 ? "" : "s"} for &ldquo;
          {submittedQuery}&rdquo;
        </p>
      )}

      {!loading && submittedQuery && (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <DocumentResultsTable
            documents={documents}
            emptyMessage="No documents matched your search."
          />
        </div>
      )}

      {!submittedQuery && !loading && (
        <p className="text-sm text-slate-400">
          Search across filenames, contract numbers, and extracted
          contract text.
        </p>
      )}
    </div>
  );
}
