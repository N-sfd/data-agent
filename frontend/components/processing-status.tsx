import { CheckCircle2, Circle, ScanText } from "lucide-react";

import type { ExtractionSummary, UploadedDocument } from "@/types/document";

interface ProcessingStatusProps {
  document: UploadedDocument;
  extraction: ExtractionSummary | null;
  extracting: boolean;
  schemaTargetCount?: number | null;
}

export default function ProcessingStatus({
  document,
  extraction,
  extracting,
  schemaTargetCount = null,
}: ProcessingStatusProps) {
  const extractionComplete = Boolean(extraction);
  const ocrRequired = extraction?.ocr_required_pages ?? 0;
  const ocrCompleted = extraction?.ocr_completed_pages ?? 0;
  const pageTextChars =
    extraction?.page_text_chars ??
    (typeof document.ingestion_provenance?.page_text_chars === "number"
      ? document.ingestion_provenance.page_text_chars
      : null);
  const ocrExecutionComplete =
    extractionComplete && (ocrRequired === 0 || ocrCompleted >= ocrRequired);
  const textExtracted =
    extractionComplete && (pageTextChars == null || pageTextChars > 0);
  const schemaComplete =
    schemaTargetCount != null
      ? schemaTargetCount > 0
      : Boolean(
          document.ingestion_provenance?.targets_discovered != null &&
            Number(document.ingestion_provenance.targets_discovered) > 0,
        );

  return (
    <div className="mt-8 border-t border-border pt-8">
      <p className="text-sm font-medium text-foreground">Processing details</p>

      <div className="mt-5 space-y-5">
        <StatusItem
          complete
          title="Upload complete"
          description="Document received by the secure upload service."
        />

        <StatusItem
          complete
          title="Document validated"
          description={`${document.page_count} page${document.page_count === 1 ? "" : "s"} validated successfully.`}
        />

        {extracting && !extractionComplete ? (
          <>
            <SkeletonStatusRow />
            <SkeletonStatusRow />
          </>
        ) : (
          <>
            <StatusItem
              complete={extractionComplete}
              active={extracting}
              title="Page-level extraction"
              description={
                extractionComplete
                  ? `${extraction?.pages_processed} pages processed.`
                  : "Extract native text and preserve page evidence."
              }
            />

            <StatusItem
              complete={extractionComplete && ocrRequired >= 0}
              active={extracting && !extractionComplete}
              title="OCR detection"
              description={
                extractionComplete
                  ? `${ocrRequired} page${ocrRequired === 1 ? "" : "s"} required OCR.`
                  : "Detect scanned and image-based pages."
              }
            />

            <StatusItem
              complete={ocrExecutionComplete}
              active={extracting && !extractionComplete}
              title="OCR execution"
              description={
                extractionComplete
                  ? ocrRequired === 0
                    ? "OCR not required for this document."
                    : `${ocrCompleted} / ${ocrRequired} page${ocrRequired === 1 ? "" : "s"} OCR'd.`
                  : "Run Tesseract on pages that need OCR."
              }
            />

            <StatusItem
              complete={Boolean(textExtracted)}
              active={extracting && !extractionComplete}
              title="Text extracted"
              description={
                extractionComplete
                  ? pageTextChars == null
                    ? "Page text persisted."
                    : `${pageTextChars.toLocaleString()} characters extracted.`
                  : "Normalize OCR/native text onto DocumentPage rows."
              }
            />

            <StatusItem
              complete={schemaComplete}
              active={false}
              title="Schema discovery"
              description={
                schemaTargetCount != null
                  ? `${schemaTargetCount} target${schemaTargetCount === 1 ? "" : "s"} discovered.`
                  : typeof document.ingestion_provenance?.targets_discovered ===
                      "number"
                    ? `${document.ingestion_provenance.targets_discovered} target${
                        Number(
                          document.ingestion_provenance.targets_discovered,
                        ) === 1
                          ? ""
                          : "s"
                      } discovered.`
                    : "Awaiting schema discovery."
              }
            />
          </>
        )}
      </div>
    </div>
  );
}

function SkeletonStatusRow() {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 h-5 w-5 shrink-0 rounded-full skeleton" />

      <div className="flex-1">
        <div className="skeleton h-3.5 w-40 rounded" />
        <div className="skeleton mt-2 h-3 w-56 rounded" />
      </div>
    </div>
  );
}

function StatusItem({
  complete,
  active = false,
  title,
  description,
}: {
  complete: boolean;
  active?: boolean;
  title: string;
  description: string;
}) {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5">
        {complete ? (
          <CheckCircle2
            className="h-5 w-5 text-success"
            strokeWidth={1.75}
          />
        ) : active ? (
          <ScanText
            className="h-5 w-5 animate-pulse text-primary"
            strokeWidth={1.75}
          />
        ) : (
          <Circle
            className="h-5 w-5 text-border"
            strokeWidth={1.75}
          />
        )}
      </div>

      <div>
        <p className="text-sm font-medium text-foreground">{title}</p>

        <p className="mt-1 text-xs leading-5 text-text-secondary">
          {description}
        </p>
      </div>
    </div>
  );
}
