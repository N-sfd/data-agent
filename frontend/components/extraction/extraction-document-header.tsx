"use client";

import Link from "next/link";
import { Download, Plus } from "lucide-react";

import type { ContractAnalysisResult, UploadedDocument } from "@/types/document";

interface ExtractionDocumentHeaderProps {
  document: UploadedDocument;
  analysis: ContractAnalysisResult;
}

function averageConfidence(fields: ContractAnalysisResult["metadata_fields"]) {
  if (fields.length === 0) return null;
  const sum = fields.reduce((acc, f) => acc + f.confidence, 0);
  return Math.round((sum / fields.length) * 100);
}

export default function ExtractionDocumentHeader({
  document,
  analysis,
}: ExtractionDocumentHeaderProps) {
  const avg = averageConfidence(analysis.metadata_fields);

  return (
    <div className="extraction-doc-header">
      <div className="extraction-workspace-inner flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-medium text-text-dark">
            {document.original_filename}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            {document.page_count} pages · Extraction complete
            {avg !== null && ` · ${avg}% avg. confidence`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/extraction/new" className="btn-secondary py-2 text-xs">
            <Plus className="h-3.5 w-3.5" />
            New Extraction
          </Link>
          <Link
            href={`/documents/${document.document_id}/review`}
            className="btn-primary py-2 text-xs"
          >
            <Download className="h-3.5 w-3.5" />
            Open Review &amp; Export
          </Link>
        </div>
      </div>
    </div>
  );
}
