import { CheckCheck } from "lucide-react";

import ConfidenceIndicator from "@/components/confidence-indicator";

interface ExtractedRow {
  marker: number;
  label: string;
  value: string;
  confidence: number;
}

const ROWS: ExtractedRow[] = [
  { marker: 1, label: "Contract No.", value: "W912HQ-24-C-0001", confidence: 0.99 },
  { marker: 2, label: "Award Date", value: "08/19/2026", confidence: 0.97 },
  { marker: 3, label: "Total Value", value: "$1.25M", confidence: 0.94 },
];

/** Marker badge positioned at a highlighted extraction zone on the mock page. */
function ZoneMarker({ number }: { number: number }) {
  return (
    <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-white shadow-[var(--shadow-soft)]">
      {number}
    </span>
  );
}

export default function HeroExtractionPreview() {
  return (
    <div
      aria-hidden
      className="hero-extraction-preview relative mx-auto w-full max-w-[440px]"
    >
      <div className="doc-shape-layered pb-6">
        {/* Faint back layer — stacked-document effect */}
        <div
          className="doc-shape-layer-back doc-shape-corner-clip rounded-[var(--radius-card)] border border-border/40 bg-surface-soft"
          style={{ height: "18rem" }}
        />

        {/* Mock PDF page with highlighted extraction zones */}
        <div className="doc-shape-layer-front doc-shape-corner-clip rounded-[var(--radius-card)] border border-border bg-surface p-5 shadow-[var(--shadow-elevated)]">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-text-secondary">
              Contract.pdf
            </p>
            <span className="rounded-full bg-surface-soft px-2 py-0.5 text-[10px] font-medium text-text-muted">
              Page 1
            </span>
          </div>

          {/* Decorative header/body lines */}
          <div className="mt-4 space-y-2">
            <div className="h-2 w-3/5 rounded-full bg-border" />
            <div className="h-1.5 w-4/5 rounded-full bg-border/70" />
            <div className="h-1.5 w-2/3 rounded-full bg-border/70" />
          </div>

          {/* Highlighted extraction zones */}
          <div className="relative mt-4 rounded-lg border border-primary/25 bg-primary/8 px-3 py-2">
            <ZoneMarker number={1} />
            <p className="text-[10px] font-medium uppercase tracking-wide text-primary/70">
              Contract No.
            </p>
            <p className="mt-0.5 font-mono text-xs text-foreground">
              W912HQ-24-C-0001
            </p>
          </div>

          <div className="relative mt-3 rounded-lg border border-success/25 bg-success/8 px-3 py-2">
            <ZoneMarker number={2} />
            <p className="text-[10px] font-medium uppercase tracking-wide text-success/70">
              Award Date
            </p>
            <p className="mt-0.5 font-mono text-xs text-foreground">
              08/19/2026
            </p>
          </div>

          <div className="relative mt-3 rounded-lg border border-primary/25 bg-primary/8 px-3 py-2">
            <ZoneMarker number={3} />
            <p className="text-[10px] font-medium uppercase tracking-wide text-primary/70">
              Total Value
            </p>
            <p className="mt-0.5 font-mono text-xs text-foreground">$1.25M</p>
          </div>

          <div className="mt-4 space-y-1.5">
            <div className="h-1.5 w-full rounded-full bg-border/50" />
            <div className="h-1.5 w-5/6 rounded-full bg-border/50" />
          </div>
        </div>
      </div>

      {/* Extracted fields panel — layered on top, offset toward the corner */}
      <div className="relative -mt-14 ml-auto w-[82%] rounded-[var(--radius-card)] border border-border bg-surface p-4 shadow-[var(--shadow-elevated)]">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-foreground">
            Extracted fields
          </p>
          <span className="inline-flex items-center gap-1 text-[10px] font-medium text-success">
            <CheckCheck className="h-3 w-3" />
            Verified
          </span>
        </div>

        <div className="mt-3 space-y-2.5">
          {ROWS.map((row) => (
            <div
              key={row.marker}
              className="flex items-center justify-between gap-3"
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/15 text-[9px] font-semibold text-primary">
                  {row.marker}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-[11px] text-text-secondary">
                    {row.label}
                  </p>
                  <p className="truncate font-mono text-xs text-foreground">
                    {row.value}
                  </p>
                </div>
              </div>
              <ConfidenceIndicator confidence={row.confidence} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
