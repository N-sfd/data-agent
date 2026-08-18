"use client";

import { Loader2 } from "lucide-react";

import type { PageRender } from "@/types/document";

interface PdfPageViewerProps {
  render: PageRender | null;
  loading: boolean;
  error: string;
  zoom?: number;
  rotation?: 0 | 90 | 180 | 270;
}

export default function PdfPageViewer({
  render,
  loading,
  error,
  zoom = 1,
  rotation = 0,
}: PdfPageViewerProps) {
  if (loading && !render) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!render) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-slate-500">
        Select a field to view its source page.
      </div>
    );
  }

  const highlight = render.highlight;

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5">
        <p className="text-sm font-semibold text-slate-900">
          Page {render.page_number}
        </p>

        {loading && (
          <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
        )}
      </div>

      <div className="flex-1 overflow-auto bg-slate-100 p-4">
        <div
          className="relative mx-auto w-fit transition-transform"
          style={{
            transform: `scale(${zoom}) rotate(${rotation}deg)`,
            transformOrigin: "top center",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={render.image_data_url}
            alt={`Page ${render.page_number}`}
            className="block max-w-full rounded-lg border border-slate-200 shadow-sm"
          />

          {highlight && (
            <div
              className="pointer-events-none absolute rounded-sm bg-amber-300/40 ring-2 ring-amber-500"
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
  );
}
