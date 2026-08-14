"use client";

import { ShieldAlert } from "lucide-react";

interface AiProviderNoticeProps {
  show: boolean;
  provider?: string;
  model?: string | null;
}

export default function AiProviderNotice({
  show,
  provider = "gemini",
  model,
}: AiProviderNoticeProps) {
  if (!show) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100">
          <ShieldAlert className="h-5 w-5 text-amber-700" />
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">
            Development AI Provider
          </p>

          <p className="mt-1 text-sm font-semibold text-amber-950">
            {provider === "gemini"
              ? "Gemini Free Tier"
              : provider}
            {model ? ` · ${model}` : ""}
          </p>

          <p className="mt-2 text-sm leading-6 text-amber-900">
            Do not upload confidential production documents
            until an approved production AI provider is configured.
          </p>
        </div>
      </div>
    </div>
  );
}
