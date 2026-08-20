"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Clock,
  FileText,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";

import { searchDocuments } from "@/lib/documents";
import type { DocumentSummary } from "@/types/document";

interface GlobalSearchProps {
  open: boolean;
  onClose: () => void;
}

export default function GlobalSearch({ open, onClose }: GlobalSearchProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const runSearch = useCallback(async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      setDocuments([]);
      return;
    }

    setLoading(true);
    try {
      const result = await searchDocuments({ q: trimmed, limit: 6 });
      setDocuments(result.documents);
    } catch {
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setDocuments([]);
      return;
    }

    const timer = window.setTimeout(() => void runSearch(query), 250);
    return () => window.clearTimeout(timer);
  }, [open, query, runSearch]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-navy/20 px-4 pt-[10vh] backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="animate-fade-in w-full max-w-2xl overflow-hidden rounded-[20px] border border-border bg-surface shadow-[var(--shadow-elevated)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-border px-5">
          <Search className="h-4 w-4 shrink-0 text-text-secondary" />
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search anything..."
            autoFocus
            className="flex-1 py-4 text-[15px] outline-none placeholder:text-text-secondary"
          />
          <kbd className="rounded-md border border-border px-1.5 py-0.5 text-[10px] text-text-secondary">
            Esc
          </kbd>
        </div>

        <div className="max-h-[440px] overflow-y-auto p-3">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching...
            </div>
          )}

          {!loading && query.trim() && documents.length === 0 && (
            <p className="py-10 text-center text-sm text-text-secondary">
              No results for &ldquo;{query.trim()}&rdquo;
            </p>
          )}

          {!loading && documents.length > 0 && (
            <SearchSection title="Contracts">
              {documents.map((doc) => (
                <SearchRow
                  key={doc.document_id}
                  icon={FileText}
                  title={doc.original_filename.replace(/\.[^.]+$/, "")}
                  subtitle={`${doc.document_type ?? "Contract"}${doc.counterparty ? ` · ${doc.counterparty}` : ""}`}
                  href={`/documents/${doc.document_id}/review`}
                  onClose={onClose}
                />
              ))}
            </SearchSection>
          )}

          {!query.trim() && (
            <>
              <SearchSection title="Quick actions">
                <SearchRow
                  icon={Sparkles}
                  title="Ask Data Agent"
                  subtitle="Natural language contract questions"
                  onClick={() => {
                    onClose();
                    router.push("/ask");
                  }}
                />
                <SearchRow
                  icon={FileText}
                  title="Contract Repository"
                  subtitle="Browse all agreements"
                  onClick={() => {
                    onClose();
                    router.push("/repository");
                  }}
                />
              </SearchSection>
              <SearchSection title="Recent searches">
                <div className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary">
                  <Clock className="h-3.5 w-3.5" />
                  Your recent searches will appear here
                </div>
              </SearchSection>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SearchSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-2">
      <p className="px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-text-secondary">
        {title}
      </p>
      {children}
    </section>
  );
}

function SearchRow({
  icon: Icon,
  title,
  subtitle,
  href,
  onClose,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
  href?: string;
  onClose?: () => void;
  onClick?: () => void;
}) {
  const className =
    "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition duration-200 hover:bg-surface-soft";

  const content = (
    <>
      <Icon className="h-4 w-4 shrink-0 text-primary" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{title}</p>
        <p className="truncate text-xs text-text-secondary">{subtitle}</p>
      </div>
    </>
  );

  if (href) {
    return (
      <Link href={href} onClick={onClose} className={className}>
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} className={className}>
      {content}
    </button>
  );
}

export function useGlobalSearchShortcut(onOpen: () => void) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        onOpen();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpen]);
}
