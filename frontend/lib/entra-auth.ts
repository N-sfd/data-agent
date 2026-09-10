/**
 * Entra ID (MSAL) configuration for the SPA.
 *
 * Register two app registrations (or one SPA + expose API):
 * 1. SPA — redirect URI = frontend origin, enable ID tokens optional
 * 2. API — expose scope api://{api-client-id}/access_as_user
 *    App roles: DataAgent.Admin | Reviewer | Analyst | Viewer
 *
 * Env (Next.js):
 *   NEXT_PUBLIC_ENTRA_TENANT_ID
 *   NEXT_PUBLIC_ENTRA_CLIENT_ID   (SPA application/client id)
 *   NEXT_PUBLIC_ENTRA_API_SCOPE  (e.g. api://data-agent/.default or access_as_user)
 *
 * After MSAL acquires an access token for the API scope, store it:
 *   localStorage.setItem("data-agent-access-token", accessToken)
 * apiFetch will send Authorization: Bearer … and the backend validates via JWKS.
 */

export interface EntraPublicConfig {
  tenantId: string;
  clientId: string;
  apiScope: string;
  authority: string;
  configured: boolean;
}

export function getEntraPublicConfig(): EntraPublicConfig {
  const tenantId = process.env.NEXT_PUBLIC_ENTRA_TENANT_ID?.trim() ?? "";
  const clientId = process.env.NEXT_PUBLIC_ENTRA_CLIENT_ID?.trim() ?? "";
  const apiScope =
    process.env.NEXT_PUBLIC_ENTRA_API_SCOPE?.trim() ??
    (clientId ? `api://${clientId}/access_as_user` : "");

  return {
    tenantId,
    clientId,
    apiScope,
    authority: tenantId
      ? `https://login.microsoftonline.com/${tenantId}`
      : "",
    configured: Boolean(tenantId && clientId && apiScope),
  };
}

export function storeAccessToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (!token) {
    window.localStorage.removeItem("data-agent-access-token");
    return;
  }
  window.localStorage.setItem("data-agent-access-token", token);
}

export function clearDevActorId() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("data-agent-actor-id");
}
