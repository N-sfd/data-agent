"use client";

const SOURCES = [
  { id: "local", label: "Local", available: true },
  { id: "sharepoint", label: "SharePoint", available: false },
  { id: "drive", label: "Drive", available: false },
  { id: "s3", label: "S3", available: false },
] as const;

export default function ImportSourceTabs() {
  return (
    <div className="rounded-xl border border-border/80 bg-surface-soft/40 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <p className="text-sm font-medium text-foreground">Import from</p>
        <p className="text-[11px] text-text-muted">
          SharePoint, Drive, and S3 — coming soon
        </p>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {SOURCES.map((source) =>
          source.available ? (
            <span key={source.id} className="chip chip-active">
              {source.label}
            </span>
          ) : (
            <span
              key={source.id}
              aria-disabled="true"
              title={`${source.label} import is coming soon`}
              className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-full border border-dashed border-border bg-surface px-3 py-1 text-xs font-medium text-text-muted opacity-75"
            >
              {source.label}
              <span className="rounded-full bg-border/80 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-secondary">
                Soon
              </span>
            </span>
          ),
        )}
      </div>
    </div>
  );
}
