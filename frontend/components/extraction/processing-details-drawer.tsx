"use client";

import { X } from "lucide-react";

import ExtractionStatusPanel from "@/components/extraction-status-panel";
import IngestionChecklist from "@/components/ingestion-checklist";
import ProcessingStatus from "@/components/processing-status";
import type {
  ExtractionProgress,
  ExtractionSummary,
  UploadedDocument,
} from "@/types/document";

interface ProcessingDetailsDrawerProps {
  open: boolean;
  onClose: () => void;
  document: UploadedDocument;
  extraction: ExtractionSummary | null;
  extracting: boolean;
  contractAnalyzed: boolean;
  progress: ExtractionProgress | null;
  elapsedSeconds: number;
  waking: boolean;
  pipelineStage?: string | null;
}

// Everything that used to sit permanently in the right column — the
// workflow-step tracker, ingestion checklist, and processing detail
// rows — relocated here unchanged, opened on demand once extraction
// has finished so it stops occupying half the page.
export default function ProcessingDetailsDrawer({
  open,
  onClose,
  document,
  extraction,
  extracting,
  contractAnalyzed,
  progress,
  elapsedSeconds,
  waking,
  pipelineStage = null,
}: ProcessingDetailsDrawerProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-slate-950/30" onClick={onClose} />

      <div className="relative flex h-full w-full max-w-md flex-col overflow-y-auto bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-950">
            Processing Details
          </h2>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-6 space-y-6">
          <ExtractionStatusPanel
            document={document}
            extraction={extraction}
            extracting={extracting}
            contractAnalyzed={contractAnalyzed}
            progress={progress}
            elapsedSeconds={elapsedSeconds}
            waking={waking}
            pipelineStage={pipelineStage}
          />

          <IngestionChecklist steps={document.pipeline_log ?? []} />

          <ProcessingStatus
            document={document}
            extraction={extraction}
            extracting={extracting}
          />
        </div>
      </div>
    </div>
  );
}
