"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

import PdfPageViewer from "@/components/pdf-page-viewer";
import PdfToolbar from "@/components/pdf-toolbar";
import { getPageRender } from "@/lib/documents";
import type { PageRender } from "@/types/document";

export interface SourceViewRequest {
  pageNumber: number;
  highlightText?: string | null;
  label?: string;
  value?: string;
  confidence?: number;
  verified?: boolean;
}

interface SourceVerificationPanelProps {
  documentId: string;
  pageCount: number;
  request: SourceViewRequest | null;
  onRequestChange?: (request: SourceViewRequest | null) => void;
}

export default function SourceVerificationPanel({
  documentId,
  pageCount,
  request,
}: SourceVerificationPanelProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [highlightText, setHighlightText] = useState<string | null>(null);
  const [pageRender, setPageRender] = useState<PageRender | null>(null);
  const [renderLoading, setRenderLoading] = useState(false);
  const [renderError, setRenderError] = useState("");
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    if (!request) return;
    setCurrentPage(request.pageNumber);
    setHighlightText(request.highlightText ?? null);
  }, [request]);

  useEffect(() => {
    if (!documentId || !request) return;

    let active = true;

    async function loadPage() {
      setRenderLoading(true);
      setRenderError("");

      try {
        const render = await getPageRender(
          documentId,
          currentPage,
          highlightText ?? undefined,
        );
        if (active) setPageRender(render);
      } catch (error) {
        if (active) {
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
  }, [documentId, currentPage, highlightText, request]);

  if (!request) {
    return (
      <div className="flex h-full min-h-[320px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface-soft p-8 text-center">
        <p className="text-sm font-medium text-foreground">Source document</p>
        <p className="mt-1 max-w-xs text-sm leading-6 text-text-secondary">
          Click any extracted value to open the exact page with the source
          highlighted.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[420px] flex-col overflow-hidden rounded-xl border border-border bg-surface">
      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,0.42fr)_minmax(0,0.58fr)]">
        <div className="border-b border-border p-4 lg:border-b-0 lg:border-r">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
            Extracted result
          </p>
          <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
            {request.label ?? "Field"}
          </p>
          <p className="mt-1 break-all text-lg font-semibold text-foreground">
            {request.value ?? "—"}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            {request.verified !== false && (
              <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 font-semibold text-success">
                <CheckCircle2 className="h-3 w-3" />
                Verified
              </span>
            )}
            <span className="text-text-secondary">Page {request.pageNumber}</span>
            {request.confidence !== undefined && (
              <span className="text-text-muted">
                {Math.round(request.confidence * 100)}% confidence
              </span>
            )}
          </div>
        </div>

        <div className="flex min-h-0 flex-col">
          <div className="shrink-0 border-b border-border">
            <PdfToolbar
              currentPage={currentPage}
              pageCount={pageCount}
              zoom={zoom}
              onPageChange={setCurrentPage}
              onZoomChange={setZoom}
              onRotate={() => {}}
              searching={false}
              searchResults={null}
              onSearch={() => {}}
              onJumpToResult={() => {}}
            />
          </div>
          <div className="min-h-0 flex-1">
            {renderLoading && !pageRender ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
              </div>
            ) : (
              <PdfPageViewer
                render={pageRender}
                loading={renderLoading}
                error={renderError}
                zoom={zoom}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
