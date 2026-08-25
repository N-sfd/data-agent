import { CheckCircle2 } from "lucide-react";

import ExtractionLiveProgress from "@/components/extraction-live-progress";
import type {
  ExtractionProgress,
  ExtractionSummary,
  UploadedDocument,
} from "@/types/document";

interface DocumentStatusSummaryProps {
  document: UploadedDocument;
  extraction: ExtractionSummary | null;
  extracting: boolean;
  progress: ExtractionProgress | null;
  elapsedSeconds: number;
  waking: boolean;
  onOpenDetails: () => void;
}

// While extraction is running, this shows the full live experience
// (page X of Y, progress bar, elapsed time, activity feed) — the
// same ExtractionLiveProgress used before, untouched. Once it
// finishes, it collapses to a compact summary so the workspace
// doesn't stay half-occupied by a completed pipeline forever; the
// full detail is still one click away via "View processing details".
export default function DocumentStatusSummary({
  document,
  extraction,
  extracting,
  progress,
  elapsedSeconds,
  waking,
  onOpenDetails,
}: DocumentStatusSummaryProps) {
  if (extracting) {
    return (
      <ExtractionLiveProgress
        progress={progress}
        elapsedSeconds={elapsedSeconds}
        waking={waking}
      />
    );
  }

  if (extraction) {
    const checksPassed = document.pipeline_log?.length ?? 0;

    return (
      <div className="rounded-xl bg-emerald-50 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-emerald-800">
          <CheckCircle2 className="h-4 w-4" />
          Extraction complete
        </p>
        <p className="mt-1.5 text-sm text-emerald-700">
          {extraction.pages_processed} / {extraction.total_document_pages}{" "}
          pages processed
          {checksPassed > 0 &&
            ` · ${checksPassed} ingestion check${checksPassed === 1 ? "" : "s"} passed`}
        </p>

        <button
          type="button"
          onClick={onOpenDetails}
          className="mt-3 text-xs font-semibold text-emerald-800 underline underline-offset-2 hover:text-emerald-900"
        >
          View processing details
        </button>
      </div>
    );
  }

  return (
    <p className="text-sm text-text-secondary">
      Document uploaded. Extraction will begin shortly.
    </p>
  );
}
