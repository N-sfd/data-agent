import { CheckCircle2, FileText } from "lucide-react";
import Link from "next/link";

import DetectionCountChips from "@/components/detection-count-chips";
import DocumentStatusSummary from "@/components/extraction/document-status-summary";
import { hasDetectionCounts } from "@/lib/detection";
import { formatBytes } from "@/lib/format";
import type {
  ContractAnalysisResult,
  ExtractionProgress,
  ExtractionSummary,
  StructureDetectionResult,
  UploadedDocument,
} from "@/types/document";

interface DocumentOverviewProps {
  document: UploadedDocument;
  structureDetection: StructureDetectionResult | null;
  contractAnalysis: ContractAnalysisResult | null;
  extraction: ExtractionSummary | null;
  extracting: boolean;
  progress: ExtractionProgress | null;
  elapsedSeconds: number;
  waking: boolean;
  onOpenProcessingDetails: () => void;
  onViewResults?: () => void;
}

export default function DocumentOverview({
  document,
  structureDetection,
  contractAnalysis,
  extraction,
  extracting,
  progress,
  elapsedSeconds,
  waking,
  onOpenProcessingDetails,
  onViewResults,
}: DocumentOverviewProps) {
  const documentType =
    contractAnalysis?.classification.document_type ??
    structureDetection?.document_family_label ??
    null;

  return (
    <div className="editorial-card space-y-6 p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Document Overview
        </p>

        <div className="mt-3 flex items-start gap-3">
          <div className="file-icon-wrap h-11 w-11 shrink-0">
            <FileText className="h-5 w-5" strokeWidth={1.75} />
          </div>

          <div className="min-w-0">
            <h2 className="truncate text-base font-medium text-foreground">
              {document.original_filename}
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              {document.page_count} pages · {formatBytes(document.size_bytes)}
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {documentType && (
          <span className="inline-flex items-center rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-800">
            {documentType}
          </span>
        )}

        <span className="inline-flex items-center rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-800">
          {document.page_count} pages
        </span>

        {extraction && !extracting && (
          <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-3 py-1 text-xs font-semibold text-success">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Extraction Complete
          </span>
        )}
      </div>

      <div className="border-t border-border pt-5">
        <p className="text-xs font-medium text-text-muted">Status</p>
        <div className="mt-2">
          <DocumentStatusSummary
            document={document}
            extraction={extraction}
            extracting={extracting}
            progress={progress}
            elapsedSeconds={elapsedSeconds}
            waking={waking}
            onOpenDetails={onOpenProcessingDetails}
          />
        </div>
      </div>

      {structureDetection &&
        hasDetectionCounts(
          structureDetection.counts,
          structureDetection.content_stats.tables,
        ) && (
          <div className="border-t border-border pt-5">
            <p className="text-xs font-medium text-text-muted">
              Detected Content
            </p>
            <div className="mt-2">
              <DetectionCountChips
                counts={structureDetection.counts}
                tableTotal={structureDetection.content_stats.tables}
              />
            </div>
          </div>
        )}

      {contractAnalysis && (
        <div className="border-t border-border pt-5">
          <p className="text-xs font-medium text-text-muted">
            Quick Actions
          </p>
          <div className="mt-2 flex flex-col gap-2">
            {onViewResults && (
              <button
                type="button"
                onClick={onViewResults}
                className="text-left text-sm font-medium text-primary hover:underline"
              >
                Review Extraction
              </button>
            )}
            <Link
              href={`/documents/${document.document_id}/review`}
              className="text-sm font-medium text-primary hover:underline"
            >
              Open Review Workspace
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
