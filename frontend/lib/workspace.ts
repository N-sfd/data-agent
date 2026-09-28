/** This browser's document workspace. A random secret generated once and
 * sent as X-Workspace-Token on every API call; the server stores only its
 * hash as the owner of documents uploaded here, and serves an anonymous
 * caller only the documents of its own workspace. Clearing site data
 * starts a new, empty workspace. */

const STORAGE_KEY = "data-agent-workspace-token";
export const WORKSPACE_HEADER = "X-Workspace-Token";

function randomToken(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function getWorkspaceToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    let token = window.localStorage.getItem(STORAGE_KEY);
    if (!token || !/^[A-Za-z0-9_-]{32,128}$/.test(token)) {
      token = randomToken();
      window.localStorage.setItem(STORAGE_KEY, token);
    }
    return token;
  } catch {
    // Storage blocked (private mode, policy): no workspace — the server
    // then shows no documents to an anonymous caller.
    return null;
  }
}
