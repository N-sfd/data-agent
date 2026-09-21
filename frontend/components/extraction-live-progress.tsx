import { useEffect, useState } from "react";

import type {
  ExtractionProgress,
  ProcessingStageEntry,
} from "@/types/document";

interface ExtractionLiveProgressProps {
  progress: ExtractionProgress | null;
  elapsedSeconds: number;
  waking: boolean;
  pipelineStage?: string | null;
  stageHistory?: ProcessingStageEntry[] | null;
  stageTimingsMs?: Record<string, number> | null;
  pagesReused?: boolean;
  discoveryReused?: boolean;
}

const PIPELINE_STAGE_LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  queued: "Queued",
  reading_document: "Reading document",
  processing_document: "Reading document",
  rendering_ocr: "Rendering/OCR",
  running_ocr: "Rendering/OCR",
  indexing: "Indexing",
  discovering_fields: "Discovering schema",
  extracting_data: "Extracting",
  validating_results: "Validating",
  complete: "Complete",
};

const PIPELINE_ORDER = [
  "Uploaded",
  "Queued",
  "Reading document",
  "Rendering/OCR",
  "Indexing",
  "Discovering schema",
  "Extracting",
  "Validating",
  "Complete",
];

const TIMING_LABELS: Record<string, string> = {
  source_retrieval_ms: "Source retrieval",
  document_page_loading_ms: "Document/page loading",
  ocr_ms: "OCR",
  pages_ocr_ms: "Pages + OCR",
  indexing_ms: "Indexing",
  table_detection_ms: "Table detection",
  schema_discovery_ms: "Schema discovery",
  discovery_ms: "Discovery",
  extraction_ms: "Extraction",
  validation_ms: "Validation",
  db_writes_ms: "DB writes",
};

const ROTATING_MESSAGES = [
  "Reading page text...",
  "Checking for scanned pages...",
  "Running OCR where needed...",
  "Preserving source evidence...",
  "Building page-level index...",
];

const STILL_WORKING_THRESHOLD_SECONDS = 10;
const SLOW_THRESHOLD_SECONDS = 45;

interface ActivityEntry {
  id: string;
  time: string;
  text: string;
}

function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function formatDurationMs(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export default function ExtractionLiveProgress({
  progress,
  elapsedSeconds,
  waking,
  pipelineStage = null,
  stageHistory = null,
  stageTimingsMs = null,
  pagesReused = false,
  discoveryReused = false,
}: ExtractionLiveProgressProps) {
  const [messageIndex, setMessageIndex] = useState(0);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [lastChangedAt, setLastChangedAt] = useState(elapsedSeconds);
  const [prevProgress, setPrevProgress] =
    useState<ExtractionProgress | null>(null);

  const stageLabel = pipelineStage
    ? PIPELINE_STAGE_LABELS[pipelineStage] ?? pipelineStage
    : null;

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((index) => (index + 1) % ROTATING_MESSAGES.length);
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  if (progress && progress !== prevProgress) {
    const previousPage = prevProgress?.page_current ?? 0;
    const previousOcr = prevProgress?.ocr_completed_pages ?? 0;
    const timeLabel = new Date().toLocaleTimeString();
    const newEntries: ActivityEntry[] = [];

    if (progress.page_current > previousPage) {
      for (
        let page = previousPage + 1;
        page <= progress.page_current;
        page += 1
      ) {
        newEntries.push({
          id: `page-${page}`,
          time: timeLabel,
          text: `Page ${page} extracted`,
        });
      }
    }

    if (progress.ocr_completed_pages > previousOcr) {
      newEntries.push({
        id: `ocr-${progress.ocr_completed_pages}`,
        time: timeLabel,
        text: "OCR applied to a scanned page",
      });
    }

    setPrevProgress(progress);

    if (newEntries.length > 0) {
      setActivity((current) => [...current, ...newEntries].slice(-5));
      setLastChangedAt(elapsedSeconds);
    }
  }

  const hasPageTotal = Boolean(progress && progress.page_total > 0);
  const percent = progress ? Math.min(progress.percent, 100) : 0;
  const stillIdleSeconds = elapsedSeconds - lastChangedAt;
  const timingEntries = Object.entries(stageTimingsMs ?? {}).filter(
    ([, ms]) => typeof ms === "number" && ms >= 0,
  );

  return (
    <div className="mt-5 space-y-5">
      <div>
        <p className="text-sm font-medium text-foreground">
          {stageLabel ?? "Extracting document"}
        </p>

        {stageLabel && (
          <ol className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-muted">
            {PIPELINE_ORDER.map((label) => {
              const active = label === stageLabel;
              const done =
                PIPELINE_ORDER.indexOf(label) <
                PIPELINE_ORDER.indexOf(stageLabel);
              return (
                <li
                  key={label}
                  className={
                    active
                      ? "font-medium text-foreground"
                      : done
                        ? "text-text-secondary"
                        : undefined
                  }
                >
                  {label}
                </li>
              );
            })}
          </ol>
        )}

        {hasPageTotal ? (
          <p className="mt-1 text-sm text-text-secondary">
            Processing page {progress!.page_current} of{" "}
            {progress!.page_total}
          </p>
        ) : (
          <p className="mt-1 text-sm text-text-secondary">
            Large contracts may take a minute or two.
          </p>
        )}

        {(pagesReused || discoveryReused) && (
          <p className="mt-1 text-xs font-medium text-success">
            {pagesReused && discoveryReused
              ? "Reusing persisted pages and schema"
              : pagesReused
                ? "Reusing persisted page/OCR artifacts"
                : "Reusing persisted schema discovery"}
          </p>
        )}
      </div>

      <div>
        <div className="progress-violet w-full">
          {hasPageTotal ? (
            <div
              className="progress-violet-fill"
              style={{ width: `${percent}%` }}
            />
          ) : (
            <div className="progress-violet-fill w-1/3 animate-[indeterminate_1.4s_ease-in-out_infinite]" />
          )}
        </div>

        {hasPageTotal && (
          <p className="mt-1.5 text-xs font-medium text-text-secondary">
            {percent}% complete
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-text-secondary">
        <span>
          Elapsed{" "}
          <span className="font-medium text-foreground">
            {formatElapsed(elapsedSeconds)}
          </span>
        </span>

        {hasPageTotal && (
          <span>
            Pages processed{" "}
            <span className="font-medium text-foreground">
              {progress!.page_current} / {progress!.page_total}
            </span>
          </span>
        )}
      </div>

      {stageHistory && stageHistory.length > 0 && (
        <div>
          <p className="text-xs font-medium text-text-muted">
            Processing stages
          </p>
          <ul className="mt-2 space-y-1">
            {stageHistory.map((entry, index) => (
              <li
                key={`${entry.stage}-${entry.at}-${index}`}
                className="flex justify-between gap-3 text-xs text-text-secondary"
              >
                <span>
                  {PIPELINE_STAGE_LABELS[entry.stage] ?? entry.stage}
                </span>
                <span className="font-medium text-foreground tabular-nums">
                  {typeof entry.duration_ms === "number"
                    ? formatDurationMs(entry.duration_ms)
                    : "—"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {timingEntries.length > 0 && (
        <div>
          <p className="text-xs font-medium text-text-muted">
            Stage timings
          </p>
          <ul className="mt-2 space-y-1">
            {timingEntries.map(([key, ms]) => (
              <li
                key={key}
                className="flex justify-between gap-3 text-xs text-text-secondary"
              >
                <span>{TIMING_LABELS[key] ?? key}</span>
                <span className="font-medium text-foreground tabular-nums">
                  {formatDurationMs(ms)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="rounded-xl bg-surface-soft px-3.5 py-2.5 text-xs text-text-secondary">
        {waking
          ? "Waking processing service..."
          : stillIdleSeconds > SLOW_THRESHOLD_SECONDS
            ? "This is taking longer than usual. The backend is still processing the document — you can keep this page open."
            : stillIdleSeconds > STILL_WORKING_THRESHOLD_SECONDS
              ? "Still working... large or complex pages may take longer to process."
              : ROTATING_MESSAGES[messageIndex]}
      </div>

      {activity.length > 0 && (
        <div>
          <p className="text-xs font-medium text-text-muted">
            Live activity
          </p>

          <ul className="mt-2 space-y-1">
            {activity.map((entry) => (
              <li
                key={entry.id}
                className="animate-fade-in text-xs text-text-secondary"
              >
                <span className="text-text-muted">{entry.time}</span>{" "}
                {entry.text}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
