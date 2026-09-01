"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";

import { API_URL, probeBackend } from "@/lib/api";

export default function BackendStatusBanner() {
  const [checking, setChecking] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [retryable, setRetryable] = useState(true);

  const runProbe = useCallback(async () => {
    setChecking(true);
    const result = await probeBackend();
    setChecking(false);

    if (result.state === "healthy") {
      setMessage(null);
      return;
    }

    setMessage(result.message);
    setRetryable(result.retryable);
  }, []);

  useEffect(() => {
    void runProbe();
  }, [runProbe]);

  if (!message) {
    return null;
  }

  return (
    <div className="mb-6 rounded-2xl border border-warning/30 bg-warning/5 p-4 text-sm text-warning">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground">Processing service unavailable</p>
          <p className="mt-1 text-xs leading-5 text-text-secondary">{message}</p>
          <p className="mt-2 text-[11px] text-text-muted">
            API endpoint: <span className="font-mono">{API_URL}</span>
          </p>
          {retryable && (
            <button
              type="button"
              onClick={() => void runProbe()}
              disabled={checking}
              className="btn-secondary mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
            >
              {checking ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Check again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
