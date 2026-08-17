"use client";

const SOURCES = ["Local", "SharePoint", "Drive", "S3"] as const;

export default function ImportSourceTabs() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-medium text-slate-500">
        Import from
      </span>

      <div className="flex flex-wrap gap-2">
        {SOURCES.map((source) =>
          source === "Local" ? (
            <span
              key={source}
              className="rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white"
            >
              {source}
            </span>
          ) : (
            <span
              key={source}
              aria-disabled="true"
              title="Coming soon"
              className="cursor-not-allowed rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-400"
            >
              {source}
            </span>
          ),
        )}
      </div>
    </div>
  );
}
