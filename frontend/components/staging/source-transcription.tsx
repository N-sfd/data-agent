"use client";

import { useEffect, useState } from "react";

import { getDocumentPages } from "@/lib/documents";
import type { DocumentPage } from "@/types/document";

/** Secondary inspection view: the raw native/OCR transcription the
 * workbook was built from. Deliberately not the primary result — the
 * staging workbook is. */
export default function SourceTranscription({ documentId }: { documentId: string }) {
  const [pages, setPages] = useState<DocumentPage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pageIndex, setPageIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getDocumentPages(documentId)
      .then((result) => {
        if (!cancelled) setPages(result);
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load the source transcription.");
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  if (error) {
    return <p className="rounded-xl border border-border p-6 text-sm text-danger">{error}</p>;
  }
  if (!pages) {
    return (
      <p className="rounded-xl border border-border p-6 text-sm text-text-secondary">
        Loading transcription...
      </p>
    );
  }
  if (pages.length === 0) {
    return (
      <p className="rounded-xl border border-border p-6 text-sm text-text-secondary">
        No transcribed text is available for this document.
      </p>
    );
  }

  const current = pages[Math.min(pageIndex, pages.length - 1)];
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary">
        <label className="flex items-center gap-2">
          Page
          <select
            value={pageIndex}
            onChange={(event) => setPageIndex(Number(event.target.value))}
            className="rounded-md border border-border bg-surface px-2 py-1 text-foreground"
          >
            {pages.map((page, index) => (
              <option key={page.page_number} value={index}>
                {page.page_label || page.page_number}
              </option>
            ))}
          </select>
          of {pages.length}
        </label>
        <span>
          {current.extraction_method} · {current.word_count} words
        </span>
      </div>
      <pre className="max-h-[65vh] overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-surface-soft p-4 font-mono text-xs text-foreground">
        {current.final_text || "(no text on this page)"}
      </pre>
    </div>
  );
}
