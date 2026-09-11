import { Check } from "lucide-react";

import ExtractionLiveProgress from "@/components/extraction-live-progress";
import type {
  ExtractionProgress,
  ExtractionSummary,
  UploadedDocument,
} from "@/types/document";

interface ExtractionStatusPanelProps {
  document: UploadedDocument | null;
  extraction: ExtractionSummary | null;
  extracting: boolean;
  contractAnalyzed: boolean;
  progress?: ExtractionProgress | null;
  elapsedSeconds?: number;
  waking?: boolean;
  pipelineStage?: string | null;
}

const WORKFLOW_STEPS = [
  { id: "upload", label: "Upload" },
  { id: "extract", label: "Extract" },
  { id: "classify", label: "Classify" },
  { id: "review", label: "Review" },
  { id: "repository", label: "Repository" },
];

export default function ExtractionStatusPanel({
  document,
  extraction,
  extracting,
  contractAnalyzed,
  progress = null,
  elapsedSeconds = 0,
  waking = false,
  pipelineStage = null,
}: ExtractionStatusPanelProps) {
  const currentStep = !document
    ? 0
    : extracting
      ? 1
      : !extraction
        ? 1
        : !contractAnalyzed
          ? 2
          : 3;

  const statusTitle = !document
    ? "Waiting for document"
    : extracting
      ? null
      : extraction && contractAnalyzed
        ? "Extraction complete"
        : extraction
          ? "Extraction ready"
          : "Document uploaded";

  const statusDetail = !document
    ? "Upload a contract to begin extraction."
    : extracting
      ? null
      : extraction && contractAnalyzed
        ? "Open the review workspace to validate extracted fields."
        : extraction
          ? "Run contract analysis to classify and extract metadata."
          : "Ready to extract pages from your document.";

  return (
    <div>
      <p className="text-base font-medium text-foreground">Extraction Status</p>

      {statusTitle && (
        <p className="mt-1 text-sm font-medium text-foreground">
          {statusTitle}
        </p>
      )}

      {statusDetail && (
        <p className="mt-1 text-sm leading-6 text-text-secondary">
          {statusDetail}
        </p>
      )}

      {extracting && (
        <ExtractionLiveProgress
          progress={progress}
          elapsedSeconds={elapsedSeconds}
          waking={waking}
          pipelineStage={pipelineStage}
        />
      )}

      <ol className="mt-8 space-y-3">
        {WORKFLOW_STEPS.map((step, index) => {
          const done = index < currentStep;
          const active = index === currentStep;
          const isExtractStep = step.id === "extract";
          const hasPageTotal = Boolean(
            progress && progress.page_total > 0,
          );

          return (
            <li key={step.id} className="flex items-start gap-3">
              <span
                className={[
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                  done
                    ? "bg-success/10 text-success"
                    : active
                      ? "bg-primary text-white"
                      : "bg-surface-soft text-text-muted",
                ].join(" ")}
              >
                {done ? (
                  <Check className="h-3.5 w-3.5" strokeWidth={2} />
                ) : active ? (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-text-muted/60" />
                )}
              </span>

              <div>
                <span
                  className={[
                    "text-sm",
                    done || active
                      ? "font-medium text-foreground"
                      : "text-text-muted",
                  ].join(" ")}
                >
                  {step.label}
                </span>

                {active && isExtractStep && extracting && hasPageTotal && (
                  <p className="mt-0.5 text-xs text-text-secondary">
                    Processing page {progress!.page_current} of{" "}
                    {progress!.page_total}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
