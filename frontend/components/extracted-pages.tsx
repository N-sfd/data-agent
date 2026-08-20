"use client";

import { useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  FileSearch,
  Loader2,
  ScanText,
} from "lucide-react";

import type { DocumentPage } from "@/types/document";

interface ExtractedPagesProps {
  pages: DocumentPage[];
  extracting?: boolean;
  error?: string;
  onRetry?: () => void;
}

export default function ExtractedPages({
  pages,
  extracting = false,
  error = "",
  onRetry,
}: ExtractedPagesProps) {
  const [expandedPage, setExpandedPage] =
    useState<number | null>(
      pages.length > 0 ? pages[0].page_number : null,
    );

  useEffect(() => {
    if (pages.length > 0 && expandedPage === null) {
      setExpandedPage(pages[0].page_number);
    }
  }, [pages, expandedPage]);

  if (extracting) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-blue-600" />

        <p className="mt-3 font-medium text-slate-700">
          Extracting pages
        </p>

        <p className="mt-1 text-sm text-slate-500">
          Reading text from the uploaded document. This can
          take a moment for large PDFs.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-white p-8 text-center shadow-sm">
        <FileSearch className="mx-auto h-8 w-8 text-red-400" />

        <p className="mt-3 font-medium text-slate-700">
          Page extraction failed
        </p>

        <p className="mt-1 text-sm text-red-600">{error}</p>

        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Retry extraction
          </button>
        )}
      </div>
    );
  }

  if (pages.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <FileSearch className="mx-auto h-8 w-8 text-slate-300" />

        <p className="mt-3 font-medium text-slate-700">
          Your document is ready to analyze
        </p>

        <p className="mt-1 text-sm text-slate-500">
          Run extraction to identify fields, clauses, tables, and contract
          relationships.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-6 py-5">
        <h2 className="text-lg font-semibold text-slate-950">
          Extracted pages
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          {pages.length} page records with source references.
        </p>
      </div>

      <div className="divide-y divide-slate-100">
        {pages.map((page) => {
          const expanded =
            expandedPage === page.page_number;

          return (
            <div key={page.page_number}>
              <button
                type="button"
                onClick={() =>
                  setExpandedPage(
                    expanded ? null : page.page_number,
                  )
                }
                className="flex w-full items-center gap-4 px-6 py-4 text-left hover:bg-slate-50"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-sm font-semibold text-slate-700">
                  {page.page_number}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-slate-900">
                      Page {page.page_number}
                    </p>

                    {page.extraction_method === "ocr" && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
                        <ScanText className="h-3 w-3" />
                        OCR
                      </span>
                    )}

                    {page.requires_ocr &&
                      !page.ocr_succeeded && (
                        <span className="rounded-full bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
                          OCR needed
                        </span>
                      )}
                  </div>

                  <p className="mt-1 truncate text-sm text-slate-500">
                    {page.word_count} words ·{" "}
                    {page.source_reference}
                  </p>
                </div>

                {expanded ? (
                  <ChevronUp className="h-5 w-5 text-slate-400" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-slate-400" />
                )}
              </button>

              {expanded && (
                <div className="bg-slate-50 px-6 py-5">
                  <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-5 text-sm leading-7 text-slate-700">
                    {page.final_text ||
                      "No machine-readable text was extracted from this page."}
                  </div>

                  <p className="mt-3 text-xs text-slate-400">
                    Source: {page.source_reference}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}