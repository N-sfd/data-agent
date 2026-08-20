"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  FileText,
  Loader2,
  Sparkles,
} from "lucide-react";

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
          <div className="mt-12 space-y-4">
            <div className="skeleton h-5 w-2/3" />
            <div className="skeleton h-4 w-1/2" />
            <div className="skeleton h-24 w-full rounded-2xl" />
          </div>
        )}

        {response && !loading && (
          <div className="mt-14 animate-fade-in space-y-8">
            <section>
              <p className="text-xs uppercase tracking-wider text-text-secondary">
                Answer
              </p>
              <p className="mt-3 text-xl font-medium leading-relaxed text-foreground">
                {response.summary}
              </p>
              {response.findings.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {response.findings.map((finding) => (
                    <li
                      key={finding}
                      className="text-[15px] leading-7 text-text-secondary"
                    >
                      {finding}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {response.contractCount > 0 && (
              <>
                <section className="editorial-card p-6">
                  <p className="text-sm text-text-secondary">Sources</p>
                  <p className="mt-1 text-2xl font-medium text-foreground">
                    {response.contractCount} contracts
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link
                      href={`/search?q=${encodeURIComponent(response.searchQuery)}`}
                      className="btn-primary"
                    >
                      View results
                    </Link>
                    <Link href="/explorer" className="btn-secondary">
                      Open in Field Explorer
                    </Link>
                  </div>
                </section>

                <section>
                  <p className="mb-4 text-sm text-text-secondary">
                    Source evidence
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
                          <p className="truncate text-sm text-text-secondary">
                            {doc.document_type ?? "Contract"}
                            {doc.counterparty ? ` · ${doc.counterparty}` : ""}
                          </p>
                        </div>
                        <ArrowRight className="h-4 w-4 shrink-0 text-text-secondary" />
                      </Link>
                    ))}
                  </div>
                </section>
              </>
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
        <div className="flex items-center justify-center py-24 text-sm text-text-secondary">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading...
        </div>
      }
    >
      <AskPageContent />
    </Suspense>
  );
}
