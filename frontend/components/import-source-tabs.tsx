"use client";

const SOURCES = [
  { id: "local", label: "Local", available: true },
  { id: "sharepoint", label: "SharePoint", available: false },
  { id: "drive", label: "Drive", available: false },
  { id: "s3", label: "S3", available: false },
] as const;

export default function ImportSourceTabs() {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-sm text-text-secondary">Import from</span>

      <div className="flex flex-wrap gap-2">
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
              className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-full border border-dashed border-border bg-surface-soft px-3 py-1 text-xs font-medium text-text-muted opacity-80"
            >
              {source.label}
              <span className="rounded-full bg-border/80 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-secondary">
                Coming soon
              </span>
            </span>
          ),
        )}
      </div>
    </div>
  );
}
