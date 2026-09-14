"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, Loader2, LogOut } from "lucide-react";

import { getCurrentActor } from "@/lib/auth";
import { storeAccessToken } from "@/lib/entra-auth";
import { ApiError } from "@/lib/api";
import type { ActorInfo } from "@/types/document";

/**
 * Stop-gap admin authentication until real Entra SSO is wired up
 * (lib/entra-auth.ts has the config surface but no login flow yet).
 * Lets someone paste a service API key issued server-side so
 * admin-only actions (like document delete) are actually reachable
 * from the browser instead of unconditionally 401ing.
 */
export default function AdminSessionKey() {
  const [actor, setActor] = useState<ActorInfo | null>(null);
  const [checking, setChecking] = useState(true);
  const [keyInput, setKeyInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const stored =
      typeof window !== "undefined"
        ? window.localStorage.getItem("data-agent-access-token")
        : null;

    if (!stored) {
      setChecking(false);
      return;
    }

    getCurrentActor()
      .then((result) => setActor(result))
      .catch(() => {
        // Stored token no longer resolves to a valid actor — clear it
        // rather than leaving a dead key silently failing every request.
        storeAccessToken(null);
        setActor(null);
      })
      .finally(() => setChecking(false));
  }, []);

  async function handleSave() {
    const trimmed = keyInput.trim();
    if (!trimmed) return;

    setSaving(true);
    setError("");

    try {
      const resolved = await getCurrentActor(trimmed);
      storeAccessToken(trimmed);
      setActor(resolved);
      setKeyInput("");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "That key wasn't recognized. Double-check it and try again."
          : err instanceof Error
            ? err.message
            : "Unable to verify this key.",
      );
    } finally {
      setSaving(false);
    }
  }

  function handleSignOut() {
    storeAccessToken(null);
    setActor(null);
    setError("");
  }

  if (checking) {
    return (
      <div className="editorial-card flex items-center gap-2 p-6 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking session…
      </div>
    );
  }

  if (actor) {
    return (
      <div className="editorial-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-success/10">
              <CheckCircle2 className="h-5 w-5 text-success" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">
                Signed in as {actor.display_name}
              </p>
              <p className="mt-0.5 text-xs text-text-secondary">
                Role: <span className="font-medium">{actor.role}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleSignOut}
            className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="editorial-card p-6">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
          <KeyRound className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">
            Admin session key
          </p>
          <p className="mt-1 text-xs leading-relaxed text-text-secondary">
            Paste a service API key issued for your account to unlock
            admin-only actions in this browser, such as deleting
            documents. This is a temporary measure until full sign-in is
            available.
          </p>

          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <input
              type="password"
              value={keyInput}
              onChange={(event) => setKeyInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") handleSave();
              }}
              placeholder="Service API key"
              disabled={saving}
              className="w-full rounded-xl border border-border bg-surface px-4 py-2.5 text-sm outline-none transition focus:border-primary/30 disabled:opacity-60"
            />
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !keyInput.trim()}
              className="btn-primary inline-flex shrink-0 items-center justify-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save
            </button>
          </div>

          {error && <p className="mt-2 text-xs text-danger">{error}</p>}
        </div>
      </div>
    </div>
  );
}
