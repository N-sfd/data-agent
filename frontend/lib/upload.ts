import { apiUrl, ApiError } from "@/lib/api";

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
 */
export function uploadFileWithProgress<T = unknown>(
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

    xhr.onerror = () => {
      reject(new Error("Cannot reach the Data Agent API — check your connection."));
    };

    xhr.send(formData);
  });
}
