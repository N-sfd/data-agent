import { apiFetch } from "@/lib/api";

export interface AiStatus {
  provider: string;
  fallback_enabled: boolean;
  mode: string;
  show_dev_warning: boolean;
  model: string | null;
}

interface HealthResponse {
  ai?: Record<string, unknown>;
}

export async function getAiStatus(): Promise<AiStatus | null> {
  try {
    const payload = await apiFetch<HealthResponse>("/health", {
      cache: "no-store",
    });

    const ai = payload.ai;

    if (!ai || typeof ai !== "object") {
      return null;
    }

    return {
      provider: String(ai.provider ?? "disabled"),
      fallback_enabled: Boolean(ai.fallback_enabled),
      mode: String(ai.mode ?? "development"),
      show_dev_warning: Boolean(ai.show_dev_warning),
      model:
        typeof ai.model === "string" ? ai.model : null,
    };
  } catch {
    return null;
  }
}
