"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileSearch,
  Loader2,
  ScanText,
} from "lucide-react";

import type { DocumentPage } from "@/types/document";

const PAGE_SIZE = 25;

type PageFilter = "all" | "ocr" | "matches" | "tables" | "clauses";

interface PaginatedPagesProps {
  pages: DocumentPage[];
  extracting?: boolean;
  error?: string;
  onRetry?: () => void;
  tablePageNumbers?: number[];
  clausePageNumbers?: number[];
}

function pageMatchesSearch(page: DocumentPage, q: string): boolean {
  if (!q) return true;
  if (String(page.page_number).includes(q)) return true;
  if (page.page_label?.toLowerCase().includes(q)) return true;
  return page.final_text.toLowerCase().includes(q);
}

function buildPageNumbers(current: number, total: number): (number | "…")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i);
  }
  const pages = new Set<number>([0, total - 1, current]);
  for (let i = current - 1; i <= current + 1; i++) {
    if (i >= 0 && i < total) pages.add(i);
  }
  const sorted = [...pages].sort((a, b) => a - b);
  const result: (number | "…")[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) result.push("…");
    result.push(sorted[i]);
  }
  return result;
}

export default function PaginatedPages({
  pages,
  extracting = false,
  error = "",
  onRetry,
  tablePageNumbers,
  clausePageNumbers,
}: PaginatedPagesProps) {
  const [pageIndex, setPageIndex] = useState(0);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<PageFilter>("all");
  const [expandedPage, setExpandedPage] = useState<number | null>(null);

  const tablePages = useMemo(
    () => new Set(tablePageNumbers ?? []),
    [tablePageNumbers],
  );
  const clausePages = useMemo(
    () => new Set(clausePageNumbers ?? []),
    [clausePageNumbers],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return pages.filter((page) => {
      if (filter === "ocr" && page.extraction_method !== "ocr") return false;
      if (filter === "tables" && !tablePages.has(page.page_number)) return false;
      if (filter === "clauses" && !clausePages.has(page.page_number))
        return false;
      if (filter === "matches") {
        if (!q) return false;
        return pageMatchesSearch(page, q);
      }
      return pageMatchesSearch(page, q);
    });
  }, [pages, search, filter, tablePages, clausePages]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safeIndex = Math.min(pageIndex, totalPages - 1);
  const sliceStart = safeIndex * PAGE_SIZE;
  const sliceEnd = sliceStart + PAGE_SIZE;
  const visible = filtered.slice(sliceStart, sliceEnd);
  const pageButtons = buildPageNumbers(safeIndex, totalPages);

  useEffect(() => {
    setPageIndex(0);
  }, [search, filter]);

  if (extracting) {
    return (
      <div className="editorial-card p-10 text-center">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
        <p className="mt-3 font-medium text-foreground">Extracting pages</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="editorial-card p-10 text-center">
        <p className="font-medium text-foreground">Page extraction failed</p>
        <p className="mt-1 text-sm text-danger">{error}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn-primary mt-4">
            Retry extraction
          </button>
        )}
      </div>
    );
  }

  if (pages.length === 0) {
    return (
      <div className="editorial-card p-10 text-center">
        <FileSearch className="mx-auto h-8 w-8 text-text-muted" />
        <p className="mt-3 text-sm text-text-secondary">No pages extracted yet.</p>
      </div>
    );
  }

  const filters: { id: PageFilter; label: string }[] = [
    { id: "all", label: "All Pages" },
    { id: "ocr", label: "OCR Pages" },
    { id: "matches", label: "Pages with Matches" },
    { id: "tables", label: "Pages with Tables" },
    { id: "clauses", label: "Pages with Clauses" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-medium text-foreground">Pages</h3>
          <p className="text-sm text-text-secondary">
            {filtered.length === pages.length
              ? `${pages.length} total pages`
              : `${filtered.length} of ${pages.length} pages`}
          </p>
        </div>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search pages..."
          className="w-full max-w-sm rounded-xl border border-border bg-surface px-4 py-2.5 text-sm outline-none focus:border-primary/30"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {filters.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setFilter(item.id)}
            className={filter === item.id ? "chip chip-active" : "chip"}
          >
            {item.label}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="py-8 text-center text-sm text-text-secondary">
          No pages match your search or filters.
        </p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-surface">
          <div className="divide-y divide-border/60">
            {visible.map((page) => {
              const expanded = expandedPage === page.page_number;
              return (
                <div key={page.page_number}>
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedPage(expanded ? null : page.page_number)
                    }
                    className="flex w-full items-center gap-4 px-4 py-2.5 text-left transition hover:bg-surface-soft/80"
                  >
                    <span className="w-10 shrink-0 text-sm tabular-nums text-text-muted">
                      {page.page_number}
                    </span>
                    <span className="min-w-0 flex-1 text-sm font-medium text-foreground">
                      Page {page.page_number}
                    </span>
                    <span className="text-sm text-text-secondary">
                      {page.word_count} words
                    </span>
                    {page.extraction_method === "ocr" && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2 py-0.5 text-[10px] font-medium text-warning">
                        <ScanText className="h-3 w-3" />
                        OCR
                      </span>
                    )}
                    {expanded ? (
                      <ChevronDown className="h-4 w-4 text-text-muted" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-text-muted" />
                    )}
                  </button>
                  {expanded && (
                    <div className="border-t border-border/60 bg-surface-soft/40 px-4 py-3">
                      <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap text-xs leading-5 text-text-secondary">
                        {page.final_text || "No text extracted."}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-text-secondary">
          <p>
            Showing {sliceStart + 1}–{Math.min(sliceEnd, filtered.length)} of{" "}
            {filtered.length}
          </p>
          {totalPages > 1 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                disabled={safeIndex === 0}
                onClick={() => setPageIndex((i) => Math.max(0, i - 1))}
                className="btn-secondary py-1.5 text-xs disabled:opacity-40"
              >
                Previous
              </button>
              {pageButtons.map((item, idx) =>
                item === "…" ? (
                  <span key={`ellipsis-${idx}`} className="px-1 text-text-muted">
                    …
                  </span>
                ) : (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setPageIndex(item)}
                    className={[
                      "min-w-8 rounded-lg px-2 py-1.5 text-xs font-medium tabular-nums",
                      safeIndex === item
                        ? "bg-surface text-text-dark shadow-sm"
                        : "text-text-secondary hover:bg-surface/70",
                    ].join(" ")}
                  >
                    {item + 1}
                  </button>
                ),
              )}
              <button
                type="button"
                disabled={safeIndex >= totalPages - 1}
                onClick={() =>
                  setPageIndex((i) => Math.min(totalPages - 1, i + 1))
                }
                className="btn-secondary py-1.5 text-xs disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
