import { CheckCircle2, FileText, RefreshCw } from "lucide-react";
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
  pipelineStage?: string | null;
  onOpenProcessingDetails: () => void;
  onViewResults?: () => void;
  onReplaceDocument?: () => void;
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
  pipelineStage = null,
  onOpenProcessingDetails,
  onViewResults,
  onReplaceDocument,
}: DocumentOverviewProps) {
  const documentType =
    contractAnalysis?.classification.document_type ??
    structureDetection?.document_family_label ??
    null;

  const showDetected =
    structureDetection &&
    hasDetectionCounts(
      structureDetection.counts,
      structureDetection.content_stats.tables,
    );

  return (
    <div className="editorial-card space-y-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
            Document Overview
          </p>
          <div className="mt-2 flex items-start gap-3">
            <div className="file-icon-wrap h-10 w-10 shrink-0">
              <FileText className="h-4 w-4" strokeWidth={1.75} />
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-sm font-medium text-foreground">
                {document.original_filename}
              </h2>
              <p className="mt-0.5 text-xs text-text-secondary">
                {document.page_count} pages · {formatBytes(document.size_bytes)}
              </p>
            </div>
          </div>
        </div>

        {onReplaceDocument && (
          <button
            type="button"
            onClick={onReplaceDocument}
            className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-text-teal hover:text-primary"
          >
            <RefreshCw className="h-3 w-3" />
            Replace
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {documentType && (
          <span className="inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-2.5 py-0.5 text-[11px] font-semibold text-primary">
            {documentType}
          </span>
        )}
        <span className="inline-flex items-center rounded-full border border-border bg-surface-soft px-2.5 py-0.5 text-[11px] font-semibold text-text-secondary">
          {document.page_count} pages
        </span>
        {extraction && !extracting && (
          <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-0.5 text-[11px] font-semibold text-success">
            <CheckCircle2 className="h-3 w-3" />
            Complete
          </span>
        )}
      </div>

      <div className="border-t border-border pt-3">
        <DocumentStatusSummary
          document={document}
          extraction={extraction}
          extracting={extracting}
          progress={progress}
          elapsedSeconds={elapsedSeconds}
          waking={waking}
          pipelineStage={pipelineStage}
          onOpenDetails={onOpenProcessingDetails}
        />
      </div>

      {showDetected && (
        <div className="border-t border-border pt-3">
          <p className="text-[11px] font-medium text-text-muted">
            Detected content
          </p>
          <div className="mt-1.5">
            <DetectionCountChips
              counts={structureDetection.counts}
              tableTotal={structureDetection.content_stats.tables}
            />
          </div>
        </div>
      )}

      {contractAnalysis && (
        <div className="border-t border-border pt-3">
          <p className="text-[11px] font-medium text-text-muted">
            Quick actions
          </p>
          <div className="mt-1.5 flex flex-col gap-1.5">
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
