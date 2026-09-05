"use client";

interface ResultSummaryBarProps {
  documentName: string;
  status: "complete" | "processing" | "failed" | "partial";
  fieldsExtracted: number;
  tablesExtracted: number;
  highConfidence: number;
  mediumConfidence: number;
  lowConfidence: number;
  validationWarnings: number;
  processingDurationMs?: number | null;
}

const STATUS_LABEL: Record<ResultSummaryBarProps["status"], string> = {
  complete: "Extraction complete",
  processing: "Extraction in progress",
  failed: "Extraction failed",
  partial: "Partial results",
};

const STATUS_TONE: Record<ResultSummaryBarProps["status"], string> = {
  complete: "bg-success/10 text-success",
  processing: "bg-primary/10 text-primary",
  failed: "bg-danger/10 text-danger",
  partial: "bg-warning/10 text-warning",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return "<1s";
  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

export default function ResultSummaryBar({
  documentName,
  status,
  fieldsExtracted,
  tablesExtracted,
  highConfidence,
  mediumConfidence,
  lowConfidence,
  validationWarnings,
  processingDurationMs,
}: ResultSummaryBarProps) {
  return (
    <div className="editorial-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-foreground">
            {documentName}
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_TONE[status]}`}
          >
            {STATUS_LABEL[status]}
          </span>
          {processingDurationMs != null && (
            <span className="text-xs text-text-secondary">
              in {formatDuration(processingDurationMs)}
            </span>
          )}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-7">
        <SummaryStat label="Fields extracted" value={fieldsExtracted} />
        <SummaryStat label="Tables extracted" value={tablesExtracted} />
        <SummaryStat label="High confidence" value={highConfidence} tone="success" />
        <SummaryStat
          label="Medium confidence"
          value={mediumConfidence}
          tone="warning"
        />
        <SummaryStat label="Low confidence" value={lowConfidence} tone="danger" />
        <SummaryStat
          label="Validation warnings"
          value={validationWarnings}
          tone={validationWarnings > 0 ? "warning" : undefined}
        />
      </div>
    </div>
  );
}

function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "success" | "warning" | "danger";
}) {
  const toneClass =
    tone === "success"
      ? "text-success"
      : tone === "warning"
        ? "text-warning"
        : tone === "danger"
          ? "text-danger"
          : "text-foreground";

  return (
    <div>
      <p className={`text-2xl font-medium tabular-nums ${toneClass}`}>{value}</p>
      <p className="mt-0.5 text-xs text-text-secondary">{label}</p>
    </div>
  );
}
