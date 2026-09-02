"use client";

import { useEffect, useRef, useState } from "react";

import { probeBackend } from "@/lib/api";

type PillState = "checking" | "ready" | "waking" | "offline";

const POLL_HEALTHY_MS = 60_000;
const POLL_UNHEALTHY_MS = 20_000;

const STATE_META: Record<
  PillState,
  { label: string; dotClass: string }
> = {
  checking: { label: "Checking…", dotClass: "bg-text-muted" },
  ready: { label: "API Ready", dotClass: "bg-success" },
  waking: { label: "Backend waking up…", dotClass: "bg-warning" },
  offline: { label: "Backend offline", dotClass: "bg-danger" },
};

export default function BackendStatusPill() {
  const [state, setState] = useState<PillState>("checking");
  const [message, setMessage] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    let active = true;

    async function check() {
      const result = await probeBackend();
      if (!active) return;

      if (result.state === "healthy") {
        setState("ready");
        setMessage(null);
        timeoutRef.current = window.setTimeout(check, POLL_HEALTHY_MS);
        return;
      }

      setState(result.retryable ? "waking" : "offline");
      setMessage(result.message);
      timeoutRef.current = window.setTimeout(check, POLL_UNHEALTHY_MS);
    }

    void check();

    return () => {
      active = false;
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const meta = STATE_META[state];

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-text-on-dark"
      title={message ?? undefined}
    >
      <span
        className={[
          "h-1.5 w-1.5 shrink-0 rounded-full",
          meta.dotClass,
          state === "checking" || state === "waking"
            ? "animate-pulse"
            : "",
        ].join(" ")}
      />
      <span className="hidden whitespace-nowrap sm:inline">
        {meta.label}
      </span>
    </span>
  );
}
