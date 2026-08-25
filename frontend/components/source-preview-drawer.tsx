"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";

import PdfPageViewer from "@/components/pdf-page-viewer";
import PdfToolbar from "@/components/pdf-toolbar";
import { getPageRender } from "@/lib/documents";
import type { PageRender } from "@/types/document";

export interface SourcePreviewRequest {
  pageNumber: number;
  highlightText?: string | null;
  label?: string;
}

interface SourcePreviewDrawerProps {
  open: boolean;
  onClose: () => void;
  documentId: string;
  pageCount: number;
  request: SourcePreviewRequest | null;
}

export default function SourcePreviewDrawer({
  open,
  onClose,
  documentId,
  pageCount,
  request,
}: SourcePreviewDrawerProps) {
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
    if (!open || !documentId) return;

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
  }, [open, documentId, currentPage, highlightText]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close source preview"
        className="absolute inset-0 bg-slate-950/40"
        onClick={onClose}
      />

      <div className="relative flex h-full w-full max-w-2xl flex-col bg-surface shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Source verification
            </p>
            <p className="mt-0.5 truncate text-sm font-medium text-foreground">
              {request?.label ?? "Document page"}
            </p>
            <p className="mt-0.5 text-xs text-text-secondary">
              Highlight shows extracted evidence on the original page
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-text-muted transition hover:bg-surface-soft hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

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
  );
}
