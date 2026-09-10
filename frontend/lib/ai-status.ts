import { apiFetch } from "@/lib/api";

export interface AiStatus {
  provider: string;
  fallback_enabled: boolean;
  mode: string;
  show_dev_warning: boolean;
  model: string | null;
}

interface ReadyResponse {
  ai?: Record<string, unknown>;
  status?: string;
}

export async function getAiStatus(): Promise<AiStatus | null> {
  try {
    // /ready carries provider config; /health stays a cheap liveness probe.
    const payload = await apiFetch<ReadyResponse>("/ready", {
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
      model: typeof ai.model === "string" ? ai.model : null,
    };
  } catch {
    return null;
  }
}
