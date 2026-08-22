import { useEffect, useState } from "react";

import type { ExtractionProgress } from "@/types/document";

interface ExtractionLiveProgressProps {
  progress: ExtractionProgress | null;
  elapsedSeconds: number;
  waking: boolean;
}

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

export default function ExtractionLiveProgress({
  progress,
  elapsedSeconds,
  waking,
}: ExtractionLiveProgressProps) {
  const [messageIndex, setMessageIndex] = useState(0);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [lastChangedAt, setLastChangedAt] = useState(elapsedSeconds);
  const [prevProgress, setPrevProgress] =
    useState<ExtractionProgress | null>(null);

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

  return (
    <div className="mt-5 space-y-5">
      <div>
        <p className="text-sm font-medium text-foreground">
          Extracting document
        </p>

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
