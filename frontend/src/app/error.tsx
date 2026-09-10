"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        Something went wrong
      </p>
      <h1 className="max-w-lg text-2xl font-semibold text-foreground">
        The workspace hit an unexpected error
      </h1>
      <p className="max-w-md text-sm text-text-secondary">
        If the API is waking from idle on Render, wait a moment and try again.
        Your documents and reviewed fields remain durable on the server.
      </p>
      <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
        <button type="button" onClick={reset} className="btn-primary">
          Try again
        </button>
        <Link href="/" className="btn-secondary">
          Back to home
        </Link>
      </div>
    </div>
  );
}
