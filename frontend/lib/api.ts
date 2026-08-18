export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

export async function apiFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  try {
    return await fetch(apiUrl(path), init);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Network error";

    if (
      message === "Failed to fetch" ||
      message === "Load failed" ||
      message === "NetworkError when attempting to fetch resource."
    ) {
      throw new Error(
        `Cannot reach the Data Agent API at ${API_URL}. Make sure the FastAPI backend is running.`,
      );
    }

    throw error;
  }
}