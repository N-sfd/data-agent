import { Check } from "lucide-react";

interface PipelineStage {
  label: string;
  complete: boolean;
  active?: boolean;
}

interface PipelineStripProps {
  classified: boolean;
  fieldsExtracted: boolean;
  humanReviewComplete: boolean;
  approved: boolean;
  promoted: boolean;
}

export default function PipelineStrip({
  classified,
  fieldsExtracted,
  humanReviewComplete,
  approved,
  promoted,
}: PipelineStripProps) {
  // Reaching the review workspace already implies upload, validation,
  // OCR, and page extraction succeeded — analyze-contract requires
  // processing_status == completed before it can run.
  const stages: PipelineStage[] = [
    { label: "Upload", complete: true },
    { label: "Validate", complete: true },
    { label: "OCR", complete: true },
    { label: "Classify", complete: classified },
    {
      label: "Extract",
      complete: fieldsExtracted,
      active: classified && !fieldsExtracted,
    },
    {
      label: "Human Review",
      complete: humanReviewComplete,
      active: fieldsExtracted && !humanReviewComplete,
    },
    {
      label: "Approve",
      complete: approved,
      active: humanReviewComplete && !approved,
    },
    {
      label: "Repository",
      complete: promoted,
      active: approved && !promoted,
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-2 text-xs">
      {stages.map((stage, index) => (
        <div key={stage.label} className="flex items-center">
          <div
            className={[
              "flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold",
              stage.complete
                ? "bg-emerald-50 text-emerald-700"
                : stage.active
                  ? "bg-blue-50 text-blue-700"
                  : "bg-slate-100 text-slate-400",
            ].join(" ")}
          >
            {stage.complete ? (
              <Check className="h-3 w-3" />
            ) : (
              <span
                className={[
                  "h-1.5 w-1.5 rounded-full",
                  stage.active ? "bg-blue-500 animate-pulse" : "bg-slate-300",
                ].join(" ")}
              />
            )}
            {stage.label}
          </div>

          {index < stages.length - 1 && (
            <span className="mx-1 text-slate-300">→</span>
          )}
        </div>
      ))}
    </div>
  );
}
