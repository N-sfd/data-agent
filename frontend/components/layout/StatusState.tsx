"use client";

import { AlertCircle, ArrowRight, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

interface LoadingStateProps {
  title?: string;
  description?: string;
  compact?: boolean;
}

export function LoadingState({
  title = "Loading data...",
  description = "Retrieving verified records and synchronizing workspace...",
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
      <div className="relative mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-surface-soft shadow-inner">
        <Loader2 className="h-7 w-7 animate-spin text-sirion-teal" />
        <div className="absolute inset-0 rounded-2xl bg-sirion-teal/5 animate-pulse" />
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-text-muted">
        {description}
      </p>
      <div className="mt-5 flex items-center gap-2 rounded-full border border-border/80 bg-surface-soft/60 px-3.5 py-1 text-[11px] text-text-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-sirion-teal animate-ping" />
        <span>Backend live sync · Source verification active</span>
      </div>
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
            Retry Connection
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
