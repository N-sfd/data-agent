import { apiUrl, ApiError, COLD_START_RETRY_DELAYS_MS } from "@/lib/api";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function sendOnce<T>(
  path: string,
  file: File,
  onProgress?: (fraction: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.open("POST", apiUrl(path));

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(event.loaded / event.total);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        if (xhr.status === 204 || !xhr.responseText) {
          resolve(undefined as T);
          return;
        }
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(new Error("The server returned an unexpected response."));
        }
        return;
      }

      reject(new ApiError(extractErrorMessageFromXhr(xhr), xhr.status));
    };

    // Fires only for a true network-level failure (connection reset, DNS,
    // CORS block, ...) — a real HTTP error status (including 502/503 from
    // a Render instance mid-restart) goes through onload above instead.
    xhr.onerror = () => {
      reject(new Error("network-error"));
    };

    xhr.send(formData);
  });
}

function extractErrorMessageFromXhr(xhr: XMLHttpRequest): string {
  let message = `API returned ${xhr.status}`;

  try {
    const body = JSON.parse(xhr.responseText);

    if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (typeof body?.detail?.message === "string") {
      message = body.detail.message;
    } else if (typeof body?.message === "string") {
      message = body.message;
    }
  } catch {
    if (xhr.responseText) {
      message = xhr.responseText;
    }
  }

  return message;
}

/**
 * Uploads a file with real byte-level progress via XMLHttpRequest — the
 * Fetch API (used by apiFetch for everything else) has no upload
 * progress event, so this is the one call site that needs XHR instead.
 *
 * Retries a true network-level failure with the same cold-start backoff
 * apiFetch uses elsewhere: a large multipart POST can still hit a
 * connection reset if it lands during a Render free-tier instance
 * restart/swap, even right after a successful wakeBackend() health
 * check moments earlier. An HTTP error status (400s/500s) is a real
 * answer from the server and is never retried here.
 */
export async function uploadFileWithProgress<T = unknown>(
  path: string,
  file: File,
  onProgress?: (fraction: number) => void,
  onRetry?: (attempt: number, total: number) => void,
): Promise<T> {
  for (
    let attempt = 0;
    attempt <= COLD_START_RETRY_DELAYS_MS.length;
    attempt += 1
  ) {
    try {
      return await sendOnce<T>(path, file, onProgress);
    } catch (error) {
      const isNetworkError =
        error instanceof Error && error.message === "network-error";
      const isLastAttempt = attempt === COLD_START_RETRY_DELAYS_MS.length;

      if (!isNetworkError || isLastAttempt) {
        if (isNetworkError) {
          throw new Error(
            "Cannot reach the Data Agent API — check your connection.",
          );
        }
        throw error;
      }

      onRetry?.(attempt + 1, COLD_START_RETRY_DELAYS_MS.length);
      onProgress?.(0);
      await sleep(COLD_START_RETRY_DELAYS_MS[attempt]);
    }
  }

  // Unreachable — the loop above always returns or throws.
  throw new Error("Cannot reach the Data Agent API — check your connection.");
}
