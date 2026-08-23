export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Render's free tier spins the backend down after ~15 minutes idle;
// the first request after that can take 30-60s to wake it. Retry
// through that window with backoff instead of surfacing an error for
// what is really just a slow cold start. A failed fetch() always
// rejects with a TypeError (network failure, DNS, CORS block, ...) —
// there is no way from JS to tell those apart, so we retry on any of
// them and only give up once the backoff window is exhausted.
const COLD_START_RETRY_DELAYS_MS = [2000, 4000, 8000, 16000, 30000];

async function fetchWithRetry(
  path: string,
  init: RequestInit | undefined,
  onRetry?: (attempt: number, total: number) => void,
): Promise<Response> {
  for (
    let attempt = 0;
    attempt <= COLD_START_RETRY_DELAYS_MS.length;
    attempt += 1
  ) {
    try {
      return await fetch(apiUrl(path), init);
    } catch (error) {
      const isLastAttempt =
        attempt === COLD_START_RETRY_DELAYS_MS.length;

      if (!(error instanceof TypeError) || isLastAttempt) {
        throw error;
      }

      onRetry?.(attempt + 1, COLD_START_RETRY_DELAYS_MS.length);

      await sleep(COLD_START_RETRY_DELAYS_MS[attempt]);
    }
  }

  // Unreachable — the loop above always returns or throws.
  throw new TypeError("Failed to fetch");
}

// Pulls the most specific message a FastAPI error response can offer:
// a plain string `detail`, a nested `detail.message` (some endpoints
// wrap validation errors this way), a top-level `message`, or — if
// the body isn't JSON at all (e.g. a raw 500 traceback page) — its
// raw text. Falls back to the HTTP status if none of that is present.
async function extractErrorMessage(
  response: Response,
): Promise<string> {
  let message = `API returned ${response.status}`;

  try {
    const body = await response.json();

    if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (typeof body?.detail?.message === "string") {
      message = body.detail.message;
    } else if (typeof body?.message === "string") {
      message = body.message;
    }
  } catch {
    const text = await response.text().catch(() => "");

    if (text) {
      message = text;
    }
  }

  return message;
}

/**
 * Fetches from the Data Agent API and returns the parsed JSON body.
 * Throws a descriptive Error on any failure so callers never have to
 * repeat response.ok / response.json() handling themselves:
 * - non-2xx response -> the backend's own error detail (or its raw
 *   text, or "API returned <status>" as a last resort)
 * - fetch() itself failing (network down, DNS, CORS block) -> a
 *   distinct "Network or CORS error" message, never confused with an
 *   application error
 */
export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit,
  onRetry?: (attempt: number, total: number) => void,
): Promise<T> {
  let response: Response;

  try {
    response = await fetchWithRetry(path, init, onRetry);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        "Network or CORS error while contacting the Data Agent API.",
      );
    }

    throw error;
  }

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
