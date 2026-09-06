"use client";

import { Loader2 } from "lucide-react";

import type { PageRender } from "@/types/document";

interface PdfPageViewerProps {
  render: PageRender | null;
  loading: boolean;
  error: string;
  zoom?: number;
  rotation?: 0 | 90 | 180 | 270;
  /** Hide the internal "Page N" bar — used when a parent (e.g. the
   * split-pane source preview) already shows document/page context. */
  hideHeader?: boolean;
}

export default function PdfPageViewer({
  render,
  loading,
  error,
  zoom = 1,
  rotation = 0,
  hideHeader = false,
}: PdfPageViewerProps) {
  if (loading && !render) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-danger">
        {error}
      </div>
    );
  }

  if (!render) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-text-secondary">
        Loading document…
      </div>
    );
  }

  const highlight = render.highlight;
  const isSideways = rotation === 90 || rotation === 270;
  const naturalWidth = render.page_width * zoom;
  const naturalHeight = render.page_height * zoom;
  // The outer box's footprint must match the POST-rotation visual size, or
  // a 90°/270° rotation paints the page mostly outside its scrollable
  // ancestor's layout bounds (CSS transforms don't reflow layout).
  const footprintWidth = isSideways ? naturalHeight : naturalWidth;
  const footprintHeight = isSideways ? naturalWidth : naturalHeight;

  return (
    <div className="flex h-full flex-col">
      {!hideHeader && (
        <div className="flex shrink-0 items-center justify-between border-b border-border bg-surface px-4 py-2.5">
          <p className="text-sm font-semibold text-foreground">
            Page {render.page_number}
          </p>

          {loading && (
            <Loader2 className="h-4 w-4 animate-spin text-text-muted" />
          )}
        </div>
      )}

      <div className="min-h-0 min-w-0 flex-1 overflow-auto bg-surface-soft p-4">
        <div
          className="relative mx-auto transition-[width,height]"
          style={{ width: footprintWidth, height: footprintHeight }}
        >
          <div
            className="absolute left-1/2 top-1/2 transition-transform"
            style={{
              width: naturalWidth,
              height: naturalHeight,
              transform: `translate(-50%, -50%) rotate(${rotation}deg)`,
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={render.image_data_url}
              alt={`Page ${render.page_number}`}
              className="block h-full w-full rounded-lg border border-border shadow-sm"
            />

            {highlight && (
              <div
                data-evidence-highlight
                className="pointer-events-none absolute rounded-sm bg-warning/30 ring-2 ring-warning"
                style={{
                  left: `${(highlight.x0 / render.page_width) * 100}%`,
                  top: `${(highlight.y0 / render.page_height) * 100}%`,
                  width: `${
                    ((highlight.x1 - highlight.x0) / render.page_width) *
                    100
                  }%`,
                  height: `${
                    ((highlight.y1 - highlight.y0) /
                      render.page_height) *
                    100
                  }%`,
                }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
