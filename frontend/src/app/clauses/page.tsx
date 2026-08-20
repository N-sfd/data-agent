"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Loader2, Search } from "lucide-react";

import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";
import { searchDocuments } from "@/lib/documents";
import type { DocumentSummary } from "@/types/document";

const CLAUSE_FILTERS = ["All", "FAR", "DFARS", "Commercial"] as const;
type ClauseFilter = (typeof CLAUSE_FILTERS)[number];

export default function ClausesPage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<ClauseFilter>("All");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!submittedQuery) return;

    let active = true;

    async function run() {
      setLoading(true);

      try {
        const result = await searchDocuments({
          q: submittedQuery,
          limit: 30,
        });
        if (active) setDocuments(result.documents);
      } catch {
        if (active) setDocuments([]);
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
    setActiveFilter("All");
    setSubmittedQuery(query.trim());
  }

  function applyFilter(filter: ClauseFilter) {
    setActiveFilter(filter);
    if (filter === "All") {
      setQuery("");
      setSubmittedQuery("");
      setDocuments([]);
      return;
    }
    setQuery(filter);
    setSubmittedQuery(filter);
  }

  return (
    <>
      <PageHero
        eyebrow="Intelligence / Clause Agent"
        title={
          <>
            Find and compare clauses
            <br />
            across every agreement
          </>
        }
        description="Search FAR, DFARS, and contract provisions across your repository with confidence and source traceability."
      />

      <ContentSection>
      <form onSubmit={handleSubmit} className="mb-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search FAR, DFARS, and contract provisions..."
            className="w-full rounded-2xl border border-border bg-surface py-3.5 pl-11 pr-4 text-[15px] outline-none focus:border-primary/30"
          />
        </div>
      </form>

      <div className="mb-6 flex flex-wrap gap-2">
        {CLAUSE_FILTERS.map((filter) => (
          <button
            key={filter}
            type="button"
            onClick={() => applyFilter(filter)}
            className={[
              "rounded-full border px-3 py-1.5 text-xs font-medium transition duration-200",
              activeFilter === filter
                ? "border-primary/30 bg-primary-soft text-primary"
                : "border-border bg-surface text-text-secondary hover:border-primary/20",
            ].join(" ")}
          >
            {filter}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 className="h-4 w-4 animate-spin" />
          Searching clauses...
        </div>
      )}

      {!loading && submittedQuery && documents.length === 0 && (
        <p className="text-sm text-text-secondary">
          No contracts found containing &ldquo;{submittedQuery}&rdquo;.
        </p>
      )}

      <div className="space-y-2">
        {documents.map((doc) => {
          const expanded = expandedId === doc.document_id;
          const title = doc.original_filename.replace(/\.[^.]+$/, "");

          return (
            <div
              key={doc.document_id}
              className="rounded-xl border border-border bg-surface"
            >
              <button
                type="button"
                onClick={() =>
                  setExpandedId(expanded ? null : doc.document_id)
                }
                className="flex w-full items-center gap-3 px-5 py-4 text-left"
              >
                {expanded ? (
                  <ChevronDown className="h-4 w-4 text-text-secondary" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-text-secondary" />
                )}
                <div className="flex-1">
                  <p className="text-sm font-semibold text-foreground">
                    {submittedQuery}
                  </p>
                  <p className="text-xs text-text-secondary">
                    Found in {title}
                    {doc.counterparty ? ` · ${doc.counterparty}` : ""}
                  </p>
                </div>
                <Link
                  href={`/documents/${doc.document_id}/review`}
                  onClick={(event) => event.stopPropagation()}
                  className="text-xs font-semibold text-brand-blue hover:underline"
                >
                  View Contract
                </Link>
              </button>

              {expanded && (
                <div className="border-t border-border px-5 py-4 text-sm text-text-secondary">
                  <p>
                    Clause reference detected in contract text. Open the contract
                    to review extracted clause details, source pages, and
                    confidence scores.
                  </p>
                  {doc.confidence !== null && (
                    <p className="mt-2 text-xs">
                      Document confidence:{" "}
                      {Math.round(doc.confidence * 100)}%
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      </ContentSection>
    </>
  );
}
