import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { uploadFileWithProgress } from "@/lib/upload";

class MockXhr {
  static instances: MockXhr[] = [];

  status = 0;
  responseText = "";
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  openedUrl = "";
  sentBody: unknown = null;

  open(_method: string, url: string) {
    this.openedUrl = url;
  }

  send(body: unknown) {
    this.sentBody = body;
    MockXhr.instances.push(this);
  }
}

describe("uploadFileWithProgress", () => {
  let originalXhr: typeof XMLHttpRequest;

  beforeEach(() => {
    originalXhr = global.XMLHttpRequest;
    MockXhr.instances = [];
    // @ts-expect-error -- test double, not a full XMLHttpRequest
    global.XMLHttpRequest = MockXhr;
  });

  afterEach(() => {
    global.XMLHttpRequest = originalXhr;
  });

  it("resolves with the parsed JSON body on success", async () => {
    const file = new File(["hello"], "test.pdf", { type: "application/pdf" });
    const promise = uploadFileWithProgress("/api/documents/upload", file);

    const xhr = MockXhr.instances[0];
    xhr.status = 201;
    xhr.responseText = JSON.stringify({ document_id: "abc-123" });
    xhr.onload?.();

    await expect(promise).resolves.toEqual({ document_id: "abc-123" });
  });

  it("reports real fractional progress as bytes are sent", async () => {
    const file = new File(["hello"], "test.pdf", { type: "application/pdf" });
    const onProgress = vi.fn();
    const promise = uploadFileWithProgress("/api/documents/upload", file, onProgress);

    const xhr = MockXhr.instances[0];
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 200 } as ProgressEvent);
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 200, total: 200 } as ProgressEvent);

    expect(onProgress).toHaveBeenNthCalledWith(1, 0.25);
    expect(onProgress).toHaveBeenNthCalledWith(2, 1);

    xhr.status = 201;
    xhr.responseText = "{}";
    xhr.onload?.();
    await promise;
  });

  it("ignores non-computable progress events instead of reporting a fake fraction", async () => {
    const file = new File(["hello"], "test.pdf", { type: "application/pdf" });
    const onProgress = vi.fn();
    const promise = uploadFileWithProgress("/api/documents/upload", file, onProgress);

    const xhr = MockXhr.instances[0];
    xhr.upload.onprogress?.({ lengthComputable: false, loaded: 50, total: 0 } as ProgressEvent);

    expect(onProgress).not.toHaveBeenCalled();

    xhr.status = 201;
    xhr.responseText = "{}";
    xhr.onload?.();
    await promise;
  });

  it("rejects with an ApiError carrying the server's error message on failure", async () => {
    const file = new File(["hello"], "test.pdf", { type: "application/pdf" });
    const promise = uploadFileWithProgress("/api/documents/upload", file);

    const xhr = MockXhr.instances[0];
    xhr.status = 422;
    xhr.responseText = JSON.stringify({ detail: "Unsupported file type." });
    xhr.onload?.();

    await expect(promise).rejects.toThrow("Unsupported file type.");
    await expect(promise.catch((e) => e)).resolves.toBeInstanceOf(ApiError);
  });

  it("retries a network error and succeeds once a later attempt connects", async () => {
    vi.useFakeTimers();
    try {
      const file = new File(["hello"], "test.pdf", { type: "application/pdf" });
      const onRetry = vi.fn();
      const promise = uploadFileWithProgress(
        "/api/documents/upload",
        file,
        undefined,
        onRetry,
      );

      expect(MockXhr.instances).toHaveLength(1);
      MockXhr.instances[0].onerror?.();

      // Let the retry's backoff delay (first entry in the schedule) elapse.
      await vi.advanceTimersByTimeAsync(2000);

      expect(onRetry).toHaveBeenCalledWith(1, expect.any(Number));
      expect(MockXhr.instances).toHaveLength(2);

      MockXhr.instances[1].status = 201;
      MockXhr.instances[1].responseText = JSON.stringify({ document_id: "abc-123" });
      MockXhr.instances[1].onload?.();

      await expect(promise).resolves.toEqual({ document_id: "abc-123" });
    } finally {
      vi.useRealTimers();
    }
  });

  it("rejects with a network error message once every retry is exhausted", async () => {
    vi.useFakeTimers();
    try {
      const file = new File(["hello"], "test.pdf", { type: "application/pdf" });
      const promise = uploadFileWithProgress("/api/documents/upload", file);
      // Swallow the rejection until we assert on it below — otherwise
      // Node logs an unhandled-rejection warning while timers advance.
      const outcome = promise.catch((e) => e);

      const delays = [2000, 4000, 8000, 16000, 30000, 45000];
      for (let i = 0; i < delays.length; i += 1) {
        MockXhr.instances[i].onerror?.();
        await vi.advanceTimersByTimeAsync(delays[i]);
      }

      // One initial attempt + one per delay.
      expect(MockXhr.instances).toHaveLength(delays.length + 1);
      MockXhr.instances[delays.length].onerror?.();

      const error = await outcome;
      expect(error).toBeInstanceOf(Error);
      expect((error as Error).message).toMatch(/cannot reach/i);
    } finally {
      vi.useRealTimers();
    }
  });
});
