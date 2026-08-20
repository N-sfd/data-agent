"use client";

const SOURCES = ["Local", "SharePoint", "Drive", "S3"] as const;

export default function ImportSourceTabs() {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-sm text-text-secondary">Import from</span>

      <div className="flex flex-wrap gap-2">
        {SOURCES.map((source) =>
          source === "Local" ? (
            <span key={source} className="chip chip-active">
              {source}
            </span>
          ) : (
            <span
              key={source}
              aria-disabled="true"
              title="Coming soon"
              className="chip cursor-not-allowed opacity-50"
            >
              {source}
            </span>
          ),
        )}
      </div>
    </div>
  );
}
