"use client";

import { ChevronDown, Download } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import OutcomeBanner from "@/components/staging/outcome-banner";
import SourceTranscription from "@/components/staging/source-transcription";
import StagingDatasetTable from "@/components/staging/staging-dataset-table";
import StagingFieldList from "@/components/staging/staging-field-list";
import { ApiError, COLD_START_RETRY_DELAYS_MS } from "@/lib/api";
import {
  downloadExport,
  getStagingWorkbook,
  type StagingDataset,
  type StagingWorkbook as Workbook,
} from "@/lib/staging-workbook";

interface StagingWorkbookProps {
  documentId: string;
  documentName?: string;
  onOpenSource?: (request: SourceViewRequest) => void;
  selectedSourceId?: string | null;
  /** Changes whenever a new extraction job completes for this document in
   * the same page session, so a workbook fetched mid-job is refetched. */
  refreshKey?: string | number;
}

type View = "workbook" | "source";

// The staging stage runs last in the extraction job; a fetch landing just
// before it finishes reports outcome "pending". Retry briefly before
// showing the pending explanation.
const PENDING_RETRY_DELAYS_MS = [2500, 4000, 6000];

function hasValues(dataset: StagingDataset): boolean {
  return dataset.records.some((record) =>
    Object.values(record.cells).some((cell) => cell.value != null),
  );
}

function initialDataset(workbook: Workbook): string {
  const business = workbook.datasets.find((d) => d.role === "business" && hasValues(d));
  const fallback =
    workbook.datasets.find((d) => d.role === "source") ??
    workbook.datasets.find((d) => d.role === "qa") ??
    workbook.datasets[0];
  return (business ?? fallback)?.dataset_id ?? "";
}

function datasetCount(dataset: StagingDataset): string {
  if (dataset.cardinality === "single") {
    const cells = Object.values(dataset.records[0]?.cells ?? {});
    const found = cells.filter((cell) => cell.value != null).length;
    return `${found}/${cells.length}`;
  }
  return String(dataset.records.length);
}

/** The Professional Staging Workbook — the primary Results experience for
 * every staging profile. */
export default function StagingWorkbook({
  documentId,
  documentName,
  onOpenSource,
  selectedSourceId,
  refreshKey,
}: StagingWorkbookProps) {
  const [workbook, setWorkbook] = useState<Workbook | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  const [view, setView] = useState<View>("workbook");
  const [activeDataset, setActiveDataset] = useState("");
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    // Render's free tier sleeps when idle and answers 502/503 (or fails
    // outright) while waking — transient, so retry through the cold-start
    // window. Real 4xx errors fail fast.
    function isTransient(err: unknown): boolean {
      return !(err instanceof ApiError) || err.status >= 500;
    }

    async function load() {
      setLoading(true);
      setError(null);
      setAuthRequired(false);
      let pendingAttempts = 0;
      let failedAttempts = 0;
      while (true) {
        let delay: number;
        try {
          const data = await getStagingWorkbook(documentId);
          if (cancelled) return;
          if (
            data.outcome.status !== "pending" ||
            pendingAttempts === PENDING_RETRY_DELAYS_MS.length
          ) {
            setWorkbook(data);
            setActiveDataset(initialDataset(data));
            setLoading(false);
            return;
          }
          delay = PENDING_RETRY_DELAYS_MS[pendingAttempts];
          pendingAttempts += 1;
        } catch (err) {
          if (cancelled) return;
          if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
            setError(
              err.status === 401
                ? "Sign-in required to view the staging workbook."
                : "Your access key doesn't have permission to view the staging workbook.",
            );
            setAuthRequired(true);
            setLoading(false);
            return;
          }
          if (!isTransient(err) || failedAttempts === COLD_START_RETRY_DELAYS_MS.length) {
            setError("Unable to load the staging workbook.");
            setLoading(false);
            return;
          }
          delay = COLD_START_RETRY_DELAYS_MS[failedAttempts];
          failedAttempts += 1;
        }
        await new Promise((resolve) => setTimeout(resolve, delay));
        if (cancelled) return;
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [documentId, refreshKey, retryTick]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setExportMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const businessDatasets = useMemo(
    () => workbook?.datasets.filter((d) => d.role === "business") ?? [],
    [workbook],
  );

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-surface-soft p-6 text-sm text-text-secondary">
        Preparing staging workbook...
      </div>
    );
  }

  if (error || !workbook) {
    return (
      <div className="space-y-3 rounded-xl border border-border bg-surface-soft p-6 text-sm">
        <p className="text-danger">{error ?? "Unable to load the staging workbook."}</p>
        {authRequired ? (
          <p className="text-text-secondary">
            Add a service API key on the{" "}
            <Link href="/api-keys" className="font-medium underline">
              API keys
            </Link>{" "}
            page, then retry.
          </p>
        ) : null}
        <button
          type="button"
          onClick={() => setRetryTick((tick) => tick + 1)}
          className="btn-secondary text-xs"
        >
          Retry
        </button>
      </div>
    );
  }

  const { profile, outcome, qa_summary: qa } = workbook;
  const dataset = workbook.datasets.find((d) => d.dataset_id === activeDataset);
  const baseName = (documentName ?? workbook.document_filename).replace(/\.[^.]+$/, "");
  const wholeExports = profile.export_capabilities.filter((c) => !c.dataset_id);
  const datasetExports = profile.export_capabilities.filter((c) => c.dataset_id);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-foreground">Professional Staging Workbook</h3>
          <p className="text-xs text-text-secondary">
            Profile:{" "}
            <span className="font-medium text-foreground">{profile.display_name}</span>{" "}
            <span className="text-text-muted">
              ({profile.profile_id}@{profile.profile_version})
            </span>
            {workbook.processing_metadata.document_family_label && (
              <> · Detected: {workbook.processing_metadata.document_family_label}</>
            )}
          </p>
          <p className="mt-0.5 text-xs text-text-secondary">
            Select any value to see its source evidence.
          </p>
        </div>
        {profile.export_capabilities.length > 0 && (
          <div className="relative" ref={exportMenuRef}>
            <button
              type="button"
              onClick={() => setExportMenuOpen((open) => !open)}
              className="btn-primary text-sm"
            >
              <Download className="h-4 w-4" />
              Export
              <ChevronDown className="h-4 w-4" />
            </button>
            {exportMenuOpen && (
              <div className="absolute right-0 top-full z-10 mt-1 w-72 rounded-lg border border-border bg-surface p-1 shadow-lg">
                {[...wholeExports, ...datasetExports].map((capability, index) => (
                  <div key={capability.href}>
                    {index === wholeExports.length && wholeExports.length > 0 && (
                      <div className="my-1 border-t border-border" />
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setExportMenuOpen(false);
                        setExportError(null);
                        downloadExport(capability, baseName).catch((err: unknown) =>
                          setExportError(err instanceof Error ? err.message : "Export failed."),
                        );
                      }}
                      className={`block w-full rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-surface-soft ${capability.dataset_id ? "" : "font-semibold"}`}
                    >
                      {capability.label}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {exportError && <p className="text-xs text-danger">{exportError}</p>}

      {outcome.status !== "populated" && <OutcomeBanner outcome={outcome} />}

      <div className="flex flex-wrap gap-x-6 gap-y-3 rounded-xl border border-border bg-surface p-4">
        {businessDatasets.map((d) => (
          <button
            key={d.dataset_id}
            type="button"
            onClick={() => {
              setView("workbook");
              setActiveDataset(d.dataset_id);
            }}
            className="text-left"
          >
            <p className="text-lg font-medium tabular-nums text-foreground">{datasetCount(d)}</p>
            <p className="mt-0.5 text-xs text-text-secondary">{d.display_name}</p>
          </button>
        ))}
        <div className="ml-auto flex gap-6 border-l border-border pl-6">
          {[
            ["Verified", qa.verified, "text-success"],
            ["Needs Review", qa.needs_review, qa.needs_review > 0 ? "text-warning" : "text-foreground"],
            ["Missing", qa.missing, "text-text-secondary"],
          ].map(([label, count, tone]) => (
            <div key={label as string}>
              <p className={`text-lg font-medium tabular-nums ${tone}`}>{count}</p>
              <p className="mt-0.5 text-xs text-text-secondary">{label} values</p>
            </div>
          ))}
        </div>
      </div>

      <div role="tablist" aria-label="Workbook views" className="flex gap-4 border-b border-border text-sm">
        {(
          [
            ["workbook", "Staging Workbook"],
            ["source", "Source / Transcription"],
          ] as [View, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={view === id}
            onClick={() => setView(id)}
            className={[
              "-mb-px border-b-2 px-1 py-2 font-medium transition",
              view === id
                ? "border-primary text-foreground"
                : "border-transparent text-text-secondary hover:text-foreground",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
      </div>

      {view === "source" ? (
        <SourceTranscription documentId={documentId} />
      ) : (
        <>
          <div
            role="tablist"
            aria-label="Datasets"
            className="flex gap-1 overflow-x-auto border-b border-border pb-px"
          >
            {workbook.datasets.map((d) => (
              <button
                key={d.dataset_id}
                type="button"
                role="tab"
                aria-selected={activeDataset === d.dataset_id}
                onClick={() => setActiveDataset(d.dataset_id)}
                className={[
                  "whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition",
                  activeDataset === d.dataset_id
                    ? "border-success text-foreground"
                    : "border-transparent text-text-secondary hover:text-foreground",
                ].join(" ")}
              >
                {d.display_name}
                <span className="ml-1.5 text-xs text-text-muted">({datasetCount(d)})</span>
              </button>
            ))}
          </div>

          {dataset?.description && (
            <p className="text-xs text-text-secondary">{dataset.description}</p>
          )}

          {dataset &&
            (dataset.cardinality === "single" ? (
              <StagingFieldList
                dataset={dataset}
                onOpenSource={onOpenSource}
                selectedId={selectedSourceId}
              />
            ) : (
              <StagingDatasetTable
                key={dataset.dataset_id}
                dataset={dataset}
                onOpenSource={onOpenSource}
                onOpenDataset={setActiveDataset}
                selectedId={selectedSourceId}
              />
            ))}
        </>
      )}
    </div>
  );
}
