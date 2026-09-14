import { apiFetch } from "@/lib/api";
import type { ActorInfo } from "@/types/document";

/**
 * Fetches the identity resolved for a bearer token. Pass `bearerToken`
 * to validate a candidate key before persisting it (apiFetch only fills
 * in the stored Authorization header when the caller didn't set one);
 * omit it to check whatever token is already stored.
 */
export async function getCurrentActor(
  bearerToken?: string,
): Promise<ActorInfo> {
  return apiFetch(
    "/api/actors/me",
    bearerToken
      ? { headers: { Authorization: `Bearer ${bearerToken}` } }
      : undefined,
  );
}
