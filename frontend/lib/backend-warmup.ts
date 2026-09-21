/**
 * Shared backend warm-up for the extraction workflow.
 *
 * Starts a single /health probe loop as soon as the extraction page mounts
 * so Render cold starts overlap with file selection. Callers join the same
 * in-flight promise — they must not start competing poll loops.
 */

import { apiUrl } from "@/lib/api";

/** Bounded exponential backoff for cold-start wake (not aggressive polling). */
export const HEALTH_BACKOFF_MS = [2000, 3000, 5000, 8000, 13000, 21000, 34000];

/** Per-attempt health timeout — short timeouts falsely mark a booting host down. */
export const HEALTH_ATTEMPT_TIMEOUT_MS = 60_000;

export type WarmupStatus =
  | "idle"
  | "warming"
  | "healthy"
  | "failed";

export interface WarmupTimings {
  pageOpenedAt: number | null;
  healthStartedAt: number | null;
  healthyAt: number | null;
  uploadStartedAt: number | null;
  uploadCompletedAt: number | null;
  processingStartedAt: number | null;
  extractionCompletedAt: number | null;
}

type StatusListener = (status: WarmupStatus) => void;

let status: WarmupStatus = "idle";
let inflight: Promise<void> | null = null;
let listeners = new Set<StatusListener>();

const timings: WarmupTimings = {
  pageOpenedAt: null,
  healthStartedAt: null,
  healthyAt: null,
  uploadStartedAt: null,
  uploadCompletedAt: null,
  processingStartedAt: null,
  extractionCompletedAt: null,
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setStatus(next: WarmupStatus) {
  status = next;
  for (const listener of listeners) {
    listener(next);
  }
}

function mark(label: string, field: keyof WarmupTimings) {
  const now = Date.now();
  timings[field] = now;
  if (typeof console !== "undefined" && console.debug) {
    const opened = timings.pageOpenedAt;
    const delta = opened != null ? ` (+${now - opened}ms)` : "";
    console.debug(`[data-agent timing] ${label}${delta}`);
  }
}

export function getWarmupStatus(): WarmupStatus {
  return status;
}

export function getWarmupTimings(): Readonly<WarmupTimings> {
  return timings;
}

export function markUploadStarted() {
  mark("file upload started", "uploadStartedAt");
}

export function markUploadCompleted() {
  mark("upload completed", "uploadCompletedAt");
}

export function markProcessingStarted() {
  mark("processing job started", "processingStartedAt");
}

export function markExtractionCompleted() {
  mark("extraction completed", "extractionCompletedAt");
}

export function subscribeWarmupStatus(listener: StatusListener): () => void {
  listeners.add(listener);
  listener(status);
  return () => {
    listeners.delete(listener);
  };
}

async function probeHealthOnce(): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    HEALTH_ATTEMPT_TIMEOUT_MS,
  );

  try {
    const response = await fetch(apiUrl("/health"), {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function runWarmupLoop(): Promise<void> {
  if (timings.pageOpenedAt == null) {
    mark("frontend page opened / warm-up begin", "pageOpenedAt");
  }
  if (timings.healthStartedAt == null) {
    mark("health request started", "healthStartedAt");
  }

  setStatus("warming");

  for (let attempt = 0; attempt <= HEALTH_BACKOFF_MS.length; attempt += 1) {
    const ok = await probeHealthOnce();
    if (ok) {
      mark("backend healthy", "healthyAt");
      setStatus("healthy");
      return;
    }

    if (attempt === HEALTH_BACKOFF_MS.length) {
      break;
    }

    await sleep(HEALTH_BACKOFF_MS[attempt]);
  }

  setStatus("failed");
  throw new Error(
    "Processing service did not become ready in time. Your file is still selected — try Upload again in a moment.",
  );
}

/**
 * Start (or join) background /health warm-up. Safe to call from page mount
 * and from the uploader — only one loop runs.
 */
export function startBackendWarmup(): Promise<void> {
  if (status === "healthy") {
    return Promise.resolve();
  }

  if (inflight) {
    return inflight;
  }

  inflight = runWarmupLoop().finally(() => {
    // Keep healthy; clear inflight so a later failure can retry.
    if (status !== "healthy") {
      inflight = null;
    }
  });

  return inflight;
}

/** Await readiness — joins the shared warm-up; does not start a second poll storm. */
export async function ensureBackendHealthy(): Promise<void> {
  if (status === "healthy") return;
  await startBackendWarmup();
  if (status !== "healthy") {
    // Loop finished as failed; allow one fresh retry cycle on explicit upload.
    inflight = null;
    await startBackendWarmup();
  }
}

/** Test helper — reset singleton state between vitest cases. */
export function __resetBackendWarmupForTests() {
  status = "idle";
  inflight = null;
  listeners = new Set();
  timings.pageOpenedAt = null;
  timings.healthStartedAt = null;
  timings.healthyAt = null;
  timings.uploadStartedAt = null;
  timings.uploadCompletedAt = null;
  timings.processingStartedAt = null;
  timings.extractionCompletedAt = null;
}
