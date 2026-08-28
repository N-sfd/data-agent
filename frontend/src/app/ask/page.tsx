"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  CheckCircle2,
  FileText,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import EmptyState from "@/components/illustrations/empty-state";
import { LoadingState } from "@/components/layout/StatusState";
import { searchDocuments } from "@/lib/documents";
import type { DocumentSummary } from "@/types/document";

const SUGGESTED = [
  "Automatic renewal clauses",
  "Contracts expiring in 90 days",
  "Net 30 payment terms",
  "DFARS clauses",
];

interface AskResponse {
  summary: string;
  findings: string[];
  contractCount: number;
  documents: DocumentSummary[];
  searchQuery: string;
}

function AskPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";

  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialQuery) {
      void runQuery(initialQuery);
    }
  }, [initialQuery]);

  async function runQuery(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;

    setLoading(true);
    setError("");
    setResponse(null);

    try {
      const result = await searchDocuments({ q: trimmed, limit: 8 });
      const count = result.total;

      const findings: string[] = [];
      if (count > 0) {
        findings.push(
          `${count} contract${count === 1 ? "" : "s"} matched your question in the repository.`,
        );
        const types = [
          ...new Set(
            result.documents
              .map((doc) => doc.document_type)
              .filter(Boolean),
          ),
        ].slice(0, 3);
        if (types.length) {
          findings.push(`Document types include ${types.join(", ")}.`);
        }
      }

      setResponse({
        summary:
          count > 0
            ? `I found ${count} contract${count === 1 ? "" : "s"} related to "${trimmed}".`
            : `I couldn't find contracts matching "${trimmed}". Try a broader term or browse the repository.`,
        findings,
        contractCount: count,
        documents: result.documents,
        searchQuery: trimmed,
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to process your question.",
      );
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    router.replace(trimmed ? `/ask?q=${encodeURIComponent(trimmed)}` : "/ask");
    void runQuery(trimmed);
  }

  return (
    <div className="page-container">
      <div className="mx-auto max-w-3xl">
        <div className="text-center">
          <p className="inline-flex items-center gap-2 text-sm font-medium text-primary-deep">
            <Sparkles className="h-4 w-4" />
            Ask Data Agent
          </p>
          <h1 className="headline-editorial mt-3">
            What would you like to know?
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="mt-10">
          <div className="ai-surface rounded-[20px] p-2">
            <div className="flex items-center gap-2 rounded-2xl bg-surface px-4 py-3">
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ask about contracts, clauses, relationships, suppliers..."
                className="flex-1 bg-transparent py-1 text-[15px] outline-none placeholder:text-text-secondary"
              />
              <button
                type="submit"
                disabled={loading}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-white transition duration-200 hover:bg-primary-hover disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
        </form>

        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {SUGGESTED.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => {
                setQuery(item);
                router.replace(`/ask?q=${encodeURIComponent(item)}`);
                void runQuery(item);
              }}
              className="chip"
            >
              {item}
            </button>
          ))}
        </div>

        {error && (
          <div className="mt-8 rounded-2xl border border-danger/20 bg-danger/5 p-4 text-sm text-danger">
            {error}
          </div>
        )}

        {loading && (
          <div className="mt-12">
            <LoadingState
              title="Querying verified repository..."
              description="Scanning extracted metadata, structured clauses, and source pages for matching evidence."
            />
          </div>
        )}

        {response && !loading && (
          <div className="mt-14 animate-fade-in space-y-8">
            <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <div className="flex items-center justify-between gap-2 border-b border-border/60 pb-3">
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-primary">
                  <Sparkles className="h-3.5 w-3.5" />
                  Grounded Intelligence Response
                </p>
                <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-0.5 text-[11px] font-medium text-success">
                  <ShieldCheck className="h-3 w-3" />
                  Verified Evidence
                </span>
              </div>
              <p className="mt-4 text-lg font-medium leading-relaxed text-foreground">
                {response.summary}
              </p>
              {response.findings.length > 0 && (
                <ul className="mt-4 space-y-2 border-t border-border/40 pt-3">
                  {response.findings.map((finding) => (
                    <li
                      key={finding}
                      className="flex items-start gap-2 text-sm leading-6 text-text-secondary"
                    >
                      <CheckCircle2 className="mt-1 h-3.5 w-3.5 shrink-0 text-success" />
                      <span>{finding}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {response.contractCount > 0 ? (
              <>
                <section className="editorial-card p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-wider text-text-secondary">Corroborating Contracts</p>
                      <p className="mt-1 text-2xl font-semibold text-foreground">
                        {response.contractCount} verified {response.contractCount === 1 ? "document" : "documents"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Link
                        href={`/search?q=${encodeURIComponent(response.searchQuery)}`}
                        className="btn-primary text-xs"
                      >
                        View in Search
                      </Link>
                      <Link href="/explorer" className="btn-secondary text-xs">
                        Field Explorer
                      </Link>
                    </div>
                  </div>
                </section>

                <section>
                  <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-secondary">
                    Source Evidence & Verification Links
                  </p>
                  <div className="space-y-3">
                    {response.documents.map((doc) => (
                      <Link
                        key={doc.document_id}
                        href={`/documents/${doc.document_id}/review`}
                        className="editorial-card flex items-center gap-4 p-5 transition duration-200 hover:shadow-[var(--shadow-elevated)]"
                      >
                        <FileText className="h-5 w-5 shrink-0 text-primary" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium text-foreground">
                            {doc.original_filename.replace(/\.[^.]+$/, "")}
                          </p>
                          <p className="truncate text-xs text-text-secondary">
                            {doc.document_type ?? "Contract"}
                            {doc.counterparty ? ` · ${doc.counterparty}` : ""}
                            {doc.page_count ? ` · ${doc.page_count} pages` : ""}
                          </p>
                        </div>
                        <span className="text-xs font-medium text-primary hover:underline flex items-center gap-1">
                          Inspect Source
                          <ArrowRight className="h-3.5 w-3.5 shrink-0" />
                        </span>
                      </Link>
                    ))}
                  </div>
                </section>
              </>
            ) : (
              <EmptyState
                variant="documents"
                title="No matching evidence found"
                description={`We searched across repository contracts but found no verified evidence for "${response.searchQuery}".`}
                action={
                  <Link href="/repository" className="btn-secondary text-xs">
                    Browse All Repository Contracts
                  </Link>
                }
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AskPage() {
  return (
    <Suspense
      fallback={
        <LoadingState
          title="Loading Ask Data Agent..."
          description="Connecting to knowledge index and conversational grounding services."
        />
      }
    >
      <AskPageContent />
    </Suspense>
  );
}
