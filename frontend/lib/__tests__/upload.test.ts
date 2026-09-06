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

  it("rejects with a network error message on xhr.onerror", async () => {
    const file = new File(["hello"], "test.pdf", { type: "application/pdf" });
    const promise = uploadFileWithProgress("/api/documents/upload", file);

    MockXhr.instances[0].onerror?.();

    await expect(promise).rejects.toThrow(/cannot reach/i);
  });
});
