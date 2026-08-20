import { CheckCircle2, Circle, ScanText } from "lucide-react";

import type { ExtractionSummary, UploadedDocument } from "@/types/document";

interface ProcessingStatusProps {
  document: UploadedDocument;
  extraction: ExtractionSummary | null;
  extracting: boolean;
}

export default function ProcessingStatus({
  document,
  extraction,
  extracting,
}: ProcessingStatusProps) {
  const extractionComplete = Boolean(extraction);

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
          complete={
            extractionComplete &&
            (extraction?.ocr_required_pages ?? 0) ===
              (extraction?.ocr_completed_pages ?? 0)
          }
          active={extracting && !extractionComplete}
          title="OCR detection"
          description={
            extractionComplete
              ? `${extraction?.ocr_required_pages ?? 0} pages required OCR.`
              : "Detect scanned and image-based pages."
          }
        />
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
