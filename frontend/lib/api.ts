export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

const NETWORK_ERROR_MESSAGES = new Set([
  "Failed to fetch",
  "Load failed",
  "NetworkError when attempting to fetch resource.",
]);

function isNetworkError(error: unknown): boolean {
  return (
    error instanceof Error && NETWORK_ERROR_MESSAGES.has(error.message)
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Render's free tier spins the backend down after ~15 minutes idle;
// the first request after that can take 30-60s to wake it. Retry
// through that window with backoff instead of surfacing an error for
// what is really just a slow cold start.
const COLD_START_RETRY_DELAYS_MS = [2000, 4000, 8000, 16000, 30000];

export async function apiFetch(
  path: string,
  init?: RequestInit,
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

      if (!isNetworkError(error) || isLastAttempt) {
        if (isNetworkError(error)) {
          throw new Error(
            `Cannot reach the Data Agent API at ${API_URL}. Make sure the FastAPI backend is running.`,
          );
        }

        throw error;
      }

      await sleep(COLD_START_RETRY_DELAYS_MS[attempt]);
    }
  }

  // Unreachable — the loop above always returns or throws.
  throw new Error(`Cannot reach the Data Agent API at ${API_URL}.`);
}