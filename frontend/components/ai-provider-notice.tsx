"use client";

import { useState } from "react";
import { ShieldAlert, X } from "lucide-react";

interface AiProviderNoticeProps {
  show: boolean;
  provider?: string;
  model?: string | null;
  fallbackEnabled?: boolean;
  mode?: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  gemini: "Gemini",
  openai: "OpenAI",
  anthropic: "Anthropic",
  disabled: "No provider configured",
};

function formatProvider(provider: string) {
  return (
    PROVIDER_LABELS[provider] ??
    provider.charAt(0).toUpperCase() + provider.slice(1)
  );
}

export default function AiProviderNotice({
  show,
  provider = "gemini",
  model,
  fallbackEnabled = false,
  mode = "development",
}: AiProviderNoticeProps) {
  const [dismissed, setDismissed] = useState(false);

  if (!show || dismissed) {
    return null;
  }

  return (
    <div
      role="alert"
      className="relative overflow-hidden rounded-2xl border border-amber-300 bg-amber-50 p-5 pl-6 shadow-sm"
    >
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-1 bg-amber-400"
      />

      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100">
          <ShieldAlert className="h-5 w-5 text-amber-700" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">
              {mode} AI provider
            </p>

            <button
              type="button"
              onClick={() => setDismissed(true)}
              aria-label="Dismiss notice"
              className="-mr-1 -mt-1 shrink-0 rounded-md p-1 text-amber-500 transition hover:bg-amber-100 hover:text-amber-800"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="mt-1 flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-amber-950">
              {formatProvider(provider)}
            </p>

            {model && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 font-mono text-xs text-amber-800">
                {model}
              </span>
            )}

            {fallbackEnabled && (
              <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-900">
                Fallback active
              </span>
            )}
          </div>

          <p className="mt-2 text-sm leading-6 text-amber-900">
            Do not upload confidential production documents until an
            approved production AI provider is configured.
          </p>
        </div>
      </div>
    </div>
  );
}
