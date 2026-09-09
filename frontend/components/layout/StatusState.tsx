"use client";

import { AlertCircle, ArrowRight, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";

interface LoadingStateProps {
  title?: string;
  description?: string;
  compact?: boolean;
}

export function LoadingState({
  title = "Loading data...",
  description = "Connecting to Data Agent…",
  compact = false,
}: LoadingStateProps) {
  if (compact) {
    return (
      <div className="flex items-center justify-center gap-3 py-8 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin text-sirion-teal" />
        <span>{title}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
      <div className="mb-6 w-full max-w-md space-y-3">
        <div className="h-4 w-3/4 animate-pulse rounded bg-border/80" />
        <div className="h-4 w-full animate-pulse rounded bg-border/60" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-border/70" />
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="h-16 animate-pulse rounded-xl bg-border/50" />
          <div className="h-16 animate-pulse rounded-xl bg-border/50" />
        </div>
      </div>
      <div className="relative mb-5 flex h-10 w-10 items-center justify-center rounded-2xl border border-border bg-surface-soft">
        <Loader2 className="h-5 w-5 animate-spin text-sirion-teal" />
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-text-muted">
        {description}
      </p>
    </div>
  );
}

export function ColdStartState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-warning/30 bg-warning/5 px-4 py-6 text-center">
      <Loader2 className="mx-auto h-6 w-6 animate-spin text-warning" />
      <h3 className="mt-3 text-sm font-semibold text-foreground">
        Processing service is waking up
      </h3>
      <p className="mt-1 text-xs text-text-secondary">
        This can take up to 60 seconds on free-tier hosting.
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="btn-secondary mt-4 text-xs"
        >
          Check again
        </button>
      )}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  error?: string;
  onRetry?: () => void;
  actionHref?: string;
  actionLabel?: string;
}

export function ErrorState({
  title = "Unable to load data",
  error = "The backend service may be starting up or temporarily unreachable.",
  onRetry,
  actionHref,
  actionLabel,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-14 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-danger/20 bg-danger/5 text-danger">
        <AlertCircle className="h-6 w-6" strokeWidth={1.75} />
      </div>
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <p className="mt-1 max-w-md text-xs leading-relaxed text-text-muted">
        {error}
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="btn-secondary inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
        )}
        {actionHref && actionLabel && (
          <Link
            href={actionHref}
            className="btn-primary inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold"
          >
            {actionLabel}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>
    </div>
  );
}
