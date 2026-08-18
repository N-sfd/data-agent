import { apiFetch } from "@/lib/api";

export interface AiStatus {
  provider: string;
  fallback_enabled: boolean;
  mode: string;
  show_dev_warning: boolean;
  model: string | null;
}

export async function getAiStatus(): Promise<AiStatus | null> {
  try {
    const response = await apiFetch("/health", {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const payload = await response.json();
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
