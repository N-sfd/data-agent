import {
    CheckCircle2,
    Circle,
    ScanText,
  } from "lucide-react";
  
  import type {
    ExtractionSummary,
    UploadedDocument,
  } from "@/types/document";
  
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
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">
          Processing status
        </h2>
  
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
            active={
              extracting &&
              !extractionComplete
            }
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
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          ) : active ? (
            <ScanText className="h-5 w-5 animate-pulse text-blue-600" />
          ) : (
            <Circle className="h-5 w-5 text-slate-300" />
          )}
        </div>
  
        <div>
          <p className="text-sm font-medium text-slate-900">
            {title}
          </p>
  
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {description}
          </p>
        </div>
      </div>
    );
  }