import { Check, Circle } from "lucide-react";

import type { ExtractionSummary, UploadedDocument } from "@/types/document";

interface ExtractionStatusPanelProps {
  document: UploadedDocument | null;
  extraction: ExtractionSummary | null;
  extracting: boolean;
  contractAnalyzed: boolean;
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
      ? "Extracting page text..."
      : extraction && contractAnalyzed
        ? "Extraction complete"
        : extraction
          ? "Extraction ready"
          : "Document uploaded";

  const statusDetail = !document
    ? "Upload a contract to begin extraction."
    : extracting
      ? "Running OCR and page-level text extraction."
      : extraction && contractAnalyzed
        ? "Open the review workspace to validate extracted fields."
        : extraction
          ? "Run contract analysis to classify and extract metadata."
          : "Ready to extract pages from your document.";

  return (
    <div>
      <p className="text-base font-medium text-foreground">Extraction Status</p>
      <p className="mt-1 text-sm font-medium text-foreground">{statusTitle}</p>
      <p className="mt-1 text-sm leading-6 text-text-secondary">
        {statusDetail}
      </p>

      <ol className="mt-8 space-y-3">
        {WORKFLOW_STEPS.map((step, index) => {
          const done = index < currentStep;
          const active = index === currentStep;

          return (
            <li key={step.id} className="flex items-center gap-3">
              <span
                className={[
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                  done
                    ? "bg-primary-soft text-primary"
                    : active
                      ? "bg-primary text-white"
                      : "bg-surface-soft text-text-muted",
                ].join(" ")}
              >
                {done ? (
                  <Check className="h-3.5 w-3.5" strokeWidth={2} />
                ) : (
                  <span>{index + 1}</span>
                )}
              </span>
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
              {active && !done && (
                <Circle className="ml-auto h-2 w-2 fill-primary text-primary animate-pulse" />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
