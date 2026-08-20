"use client";

import { useEffect, useState } from "react";
import { Loader2, Search as SearchIcon } from "lucide-react";

import DocumentResultsTable from "@/components/document-results-table";
import PageHeader from "@/components/page-header";
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
    if (!submittedQuery) return;

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
        if (active) {
          setError(err instanceof Error ? err.message : "Search failed.");
        }
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
    <div className="mx-auto max-w-5xl px-6 py-8">
      <PageHeader
        title="Search"
        description="Search across contracts, counterparties, clauses, and extracted fields."
      />

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search contracts, suppliers, clauses, fields..."
            autoFocus
            className="w-full rounded-xl border border-border bg-surface py-3 pl-11 pr-4 text-sm outline-none focus:border-brand-blue"
          />
        </div>
      </form>

      {error && (
        <div className="mb-4 rounded-xl border border-error/20 bg-error/5 p-3 text-sm text-error">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 className="h-4 w-4 animate-spin" />
          Searching repository...
        </div>
      )}

      {!loading && submittedQuery && (
        <p className="mb-3 text-xs text-text-secondary">
          {total} result{total === 1 ? "" : "s"} for &ldquo;{submittedQuery}
          &rdquo;
        </p>
      )}

      {!loading && submittedQuery && (
        <div className="overflow-hidden rounded-xl border border-border bg-surface">
          <DocumentResultsTable
            documents={documents}
            emptyMessage="No documents matched your search."
            showExtendedColumns
          />
        </div>
      )}

      {!submittedQuery && !loading && (
        <p className="text-sm text-text-secondary">
          Use global search with{" "}
          <kbd className="rounded border border-border px-1.5 py-0.5 text-xs">
            Ctrl K
          </kbd>{" "}
          from anywhere in the app.
        </p>
      )}
    </div>
  );
}
