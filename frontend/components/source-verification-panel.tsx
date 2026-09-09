"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

import PdfPageViewer from "@/components/pdf-page-viewer";
import PdfToolbar, { type SearchMatch } from "@/components/pdf-toolbar";
import { getDocumentPages, getPageRender } from "@/lib/documents";
import type { DocumentPage, PageRender } from "@/types/document";

export interface SourceViewRequest {
  /** Stable id of the selected result (FieldRow.id / table id) — used by
   * the results list to keep the clicked row visually selected. */
  id?: string;
  pageNumber: number;
  highlightText?: string | null;
  label?: string;
  value?: string;
  confidence?: number;
  verified?: boolean;
}

interface SourceVerificationPanelProps {
  documentId: string;
  documentName: string;
  pageCount: number;
  request: SourceViewRequest | null;
}

function renderCacheKey(page: number, highlight: string | null): string {
  return `${page}::${highlight ?? ""}`;
}

export default function SourceVerificationPanel({
  documentId,
  documentName,
  pageCount,
  request,
}: SourceVerificationPanelProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [highlightText, setHighlightText] = useState<string | null>(null);
  const [pageRender, setPageRender] = useState<PageRender | null>(null);
  const [renderLoading, setRenderLoading] = useState(false);
  const [renderError, setRenderError] = useState("");
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState<0 | 90 | 180 | 270>(0);

  const [documentPages, setDocumentPages] = useState<DocumentPage[] | null>(
    null,
  );
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchMatch[] | null>(
    null,
  );
  const [lastQuery, setLastQuery] = useState("");

  const viewerRef = useRef<HTMLDivElement | null>(null);
  const renderCacheRef = useRef<Map<string, PageRender>>(new Map());

  useEffect(() => {
    if (!request) return;
    setCurrentPage(request.pageNumber);
    setHighlightText(request.highlightText ?? null);
  }, [request]);

  useEffect(() => {
    if (!documentId) return;

    let active = true;
    const cacheKey = renderCacheKey(currentPage, highlightText);
    const cached = renderCacheRef.current.get(cacheKey);

    if (cached) {
      setPageRender(cached);
      setRenderError("");
    }

    async function loadPage() {
      setRenderLoading(true);
      if (!cached) setRenderError("");

      try {
        const render = await getPageRender(
          documentId,
          currentPage,
          highlightText ?? undefined,
        );
        if (!active) return;

        renderCacheRef.current.set(cacheKey, render);
        setPageRender(render);
        setRenderError("");

        // Prefetch the next plain page in the background so Next feels
        // instant, without ever keeping more than one page mounted.
        const nextPage = currentPage + 1;
        if (nextPage <= pageCount) {
          const nextKey = renderCacheKey(nextPage, null);
          if (!renderCacheRef.current.has(nextKey)) {
            getPageRender(documentId, nextPage)
              .then((nextRender) => {
                renderCacheRef.current.set(nextKey, nextRender);
              })
              .catch(() => {
                // Best-effort — the real fetch happens again on navigation.
              });
          }
        }
      } catch (error) {
        if (active && !cached) {
          setRenderError(
            error instanceof Error
              ? error.message
              : "Unable to render this page.",
          );
        }
      } finally {
        if (active) setRenderLoading(false);
      }
    }

    void loadPage();

    return () => {
      active = false;
    };
  }, [documentId, currentPage, highlightText, pageCount]);

  // Once a highlighted render loads, make sure the highlighted region is
  // actually within the visible scroll area (matters once zoomed in).
  useEffect(() => {
    if (!pageRender?.highlight) return;
    const frame = requestAnimationFrame(() => {
      viewerRef.current
        ?.querySelector("[data-evidence-highlight]")
        ?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    });
    return () => cancelAnimationFrame(frame);
  }, [pageRender]);

  function handleRotate() {
    setRotation((current) =>
      current === 270 ? 0 : ((current + 90) as 0 | 90 | 180 | 270),
    );
  }

  function handleFitWidth() {
    if (!viewerRef.current || !pageRender) return;
    const available = viewerRef.current.clientWidth - 32;
    const isSideways = rotation === 90 || rotation === 270;
    const naturalWidth = isSideways ? pageRender.page_height : pageRender.page_width;
    if (available > 0 && naturalWidth > 0) {
      setZoom(Math.max(0.5, Math.min(2.5, +(available / naturalWidth).toFixed(2))));
    }
  }

  async function handleSearch(query: string) {
    setSearching(true);
    setLastQuery(query);

    try {
      let pages = documentPages;

      if (!pages) {
        pages = await getDocumentPages(documentId);
        setDocumentPages(pages);
      }

      const needle = query.toLowerCase();

      const results: SearchMatch[] = pages
        .map((page) => {
          const haystack = page.final_text.toLowerCase();
          let count = 0;
          let index = haystack.indexOf(needle);

          while (index !== -1) {
            count += 1;
            index = haystack.indexOf(needle, index + needle.length);
          }

          return { pageNumber: page.page_number, matches: count };
        })
        .filter((result) => result.matches > 0);

      setSearchResults(results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  function handleJumpToResult(pageNumber: number) {
    setCurrentPage(pageNumber);
    setHighlightText(lastQuery);
  }

  const selectedLabel = request?.label?.trim();
  const selectedValue = request?.value?.trim();

  return (
    <div className="flex h-full min-h-[420px] flex-col overflow-hidden rounded-xl border border-primary/20 bg-surface shadow-[var(--shadow-soft)]">
      <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border bg-primary/[0.04] px-4 py-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-teal">
            Source Verification
          </p>
          <p className="mt-0.5 truncate text-sm font-semibold text-foreground">
            {documentName}
          </p>
          <p className="text-xs text-text-secondary">
            Page {currentPage} of {pageCount}
            {selectedLabel ? ` · ${selectedLabel}` : ""}
          </p>
          {selectedValue ? (
            <p className="mt-1 truncate text-xs text-foreground">
              Highlighting:{" "}
              <span className="font-medium">{selectedValue}</span>
            </p>
          ) : (
            <p className="mt-1 text-xs text-text-muted">
              Click a result to jump to its evidence in the PDF.
            </p>
          )}
        </div>
        {renderLoading && (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-text-muted" />
        )}
      </div>

      <PdfToolbar
        currentPage={currentPage}
        pageCount={pageCount}
        zoom={zoom}
        onPageChange={setCurrentPage}
        onZoomChange={setZoom}
        onFitWidth={handleFitWidth}
        onRotate={handleRotate}
        searching={searching}
        searchResults={searchResults}
        onSearch={handleSearch}
        onJumpToResult={handleJumpToResult}
      />

      <div ref={viewerRef} className="min-h-0 flex-1">
        <PdfPageViewer
          render={pageRender}
          loading={renderLoading}
          error={renderError}
          zoom={zoom}
          rotation={rotation}
          hideHeader
        />
      </div>
    </div>
  );
}
