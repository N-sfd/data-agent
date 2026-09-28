"use client";

import { useEffect, useState } from "react";

import SourceVerificationPanel, {
  type SourceViewRequest,
} from "@/components/source-verification-panel";
import { getDocumentPages, getPageTranscript } from "@/lib/documents";
import type {
  DocumentPage,
  PageTranscript,
  TranscriptBlock,
  TranscriptLine,
} from "@/types/document";

interface SourceTranscriptionProps {
  documentId: string;
  documentName?: string;
}

/** Runs of one visual line ("Roll No.   516522") are joined by the backend
 * with a wide space; render them as spaced cells rather than raw spaces. */
function LineText({ text }: { text: string }) {
  const runs = text.split("   ");
  if (runs.length === 1) return <>{text}</>;
  return (
    <span className="flex flex-wrap gap-x-6 gap-y-0.5">
      {runs.map((run, index) => (
        <span key={index}>{run}</span>
      ))}
    </span>
  );
}

/** Source & Transcript: the original page beside its reading-order
 * transcript. Clicking a transcript line highlights its source region;
 * the raw OCR text is kept only as a diagnostic. */
export default function SourceTranscription({ documentId, documentName }: SourceTranscriptionProps) {
  const [pages, setPages] = useState<DocumentPage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [transcript, setTranscript] = useState<PageTranscript | null>(null);
  const [transcriptError, setTranscriptError] = useState<string | null>(null);
  const [request, setRequest] = useState<SourceViewRequest | null>(null);
  const [selectedLine, setSelectedLine] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDocumentPages(documentId)
      .then((result) => {
        if (!cancelled) setPages(result);
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load the source transcript.");
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  const current = pages && pages.length > 0 ? pages[Math.min(pageIndex, pages.length - 1)] : null;
  const pageNumber = current?.page_number ?? null;

  useEffect(() => {
    if (pageNumber == null) return;
    let cancelled = false;
    setTranscript(null);
    setTranscriptError(null);
    setSelectedLine(null);
    setRequest({ pageNumber });
    getPageTranscript(documentId, pageNumber)
      .then((result) => {
        if (!cancelled) setTranscript(result);
      })
      .catch(() => {
        if (!cancelled) setTranscriptError("Unable to reconstruct this page's transcript.");
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, pageNumber]);

  if (error) {
    return <p className="rounded-xl border border-border p-6 text-sm text-danger">{error}</p>;
  }
  if (!pages) {
    return (
      <p className="rounded-xl border border-border p-6 text-sm text-text-secondary">
        Loading transcript...
      </p>
    );
  }
  if (!current || pageNumber == null) {
    return (
      <p className="rounded-xl border border-border p-6 text-sm text-text-secondary">
        No transcribed text is available for this document.
      </p>
    );
  }

  const isHtml = transcript?.source_type === "html";
  const textOnly = transcript?.positioning === "text_only";

  function selectLine(key: string, line: TranscriptLine) {
    if (pageNumber == null) return;
    setSelectedLine(key);
    setRequest({
      pageNumber,
      region: line.bbox,
      label: "Transcript",
      value: line.text.replaceAll("   ", " "),
    });
  }

  function renderLine(key: string, line: TranscriptLine, className: string) {
    const selected = selectedLine === key;
    return (
      <button
        key={key}
        type="button"
        disabled={isHtml || !line.bbox}
        onClick={() => selectLine(key, line)}
        className={[
          "block w-full rounded px-1.5 py-0.5 text-left transition disabled:cursor-default",
          selected ? "bg-primary/10 ring-1 ring-primary/30" : "enabled:hover:bg-surface-soft",
          className,
        ].join(" ")}
      >
        <LineText text={line.text} />
      </button>
    );
  }

  function renderBlock(block: TranscriptBlock, index: number) {
    if (block.kind === "table" && block.table) {
      const { headers, rows } = block.table;
      return (
        <div key={index} className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            {headers.length > 0 && (
              <thead className="bg-surface-soft text-xs text-text-secondary">
                <tr>
                  {headers.map((header, c) => (
                    <th key={c} className="px-2 py-1.5 text-left font-medium">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {rows.map((row, r) => {
                const key = `${index}:r${r}`;
                const line = block.lines[r];
                const selected = selectedLine === key;
                return (
                  <tr
                    key={r}
                    onClick={() => line && selectLine(key, line)}
                    className={[
                      "border-t border-border",
                      line?.bbox ? "cursor-pointer hover:bg-surface-soft" : "",
                      selected ? "bg-primary/10" : "",
                    ].join(" ")}
                  >
                    {row.map((cell, c) => (
                      <td key={c} className="px-2 py-1 align-top">
                        {cell}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }
    if (block.kind === "heading") {
      return (
        <div key={index}>
          {block.lines.map((line, l) =>
            renderLine(`${index}:${l}`, line, "text-base font-semibold text-foreground"),
          )}
        </div>
      );
    }
    return (
      <div key={index} className="space-y-0.5 text-sm leading-relaxed text-foreground">
        {block.lines.map((line, l) => renderLine(`${index}:${l}`, line, ""))}
      </div>
    );
  }

  const method = transcript?.extraction_method ?? current.extraction_method;
  const words = transcript?.word_count ?? current.word_count;

  const transcriptPane = (
    <section
      aria-label="Transcript"
      className="flex min-h-[420px] flex-col overflow-hidden rounded-xl border border-border bg-surface"
    >
      <div className="border-b border-border px-4 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-teal">
          {textOnly ? "Text-only transcription" : "Transcript"}
        </p>
        <p className="text-xs text-text-secondary">
          {textOnly
            ? "Source positioning was not available for this page. Transcript text is shown below; source highlighting is unavailable."
            : "Reading order reconstructed from the page. Click a line to highlight it in the source."}
        </p>
      </div>
      <div className="max-h-[65vh] flex-1 space-y-3 overflow-auto p-4">
        {transcriptError ? (
          <p className="text-sm text-danger">{transcriptError}</p>
        ) : !transcript ? (
          <p className="text-sm text-text-secondary">Reconstructing transcript...</p>
        ) : transcript.blocks.length === 0 ? (
          <p className="text-sm text-text-secondary">(no text on this page)</p>
        ) : (
          transcript.blocks.map(renderBlock)
        )}
      </div>
    </section>
  );

  return (
    <div className="space-y-3">
      <div className={isHtml ? "" : "grid gap-4 lg:grid-cols-2"}>
        {!isHtml && (
          <SourceVerificationPanel
            documentId={documentId}
            documentName={documentName ?? ""}
            pageCount={pages.length}
            request={request}
          />
        )}
        {transcriptPane}
      </div>

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
          {method === "ocr" ? "OCR" : method === "dom" ? "HTML" : method === "native" ? "Native text" : method} · {words}{" "}
          words
        </span>
      </div>

      <details className="rounded-xl border border-border bg-surface-soft px-4 py-2 text-xs text-text-secondary">
        <summary className="cursor-pointer select-none py-1 font-medium">Raw OCR diagnostics</summary>
        <p className="mt-1">
          The engine&apos;s raw text for this page, layout-preserving and uncorrected — for diagnosing
          extraction, not for reading.
        </p>
        <pre className="mt-2 max-h-[40vh] overflow-auto whitespace-pre-wrap font-mono text-[11px] text-foreground">
          {current.final_text || "(no text on this page)"}
        </pre>
      </details>
    </div>
  );
}
