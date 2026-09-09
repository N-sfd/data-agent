import { CheckCheck } from "lucide-react";

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

function ZoneMarker({ number }: { number: number }) {
  return (
    <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-white shadow-[var(--shadow-soft)]">
      {number}
    </span>
  );
}

function ConfidenceRing({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const radius = 10;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - confidence);

  return (
    <span
      className="relative inline-flex h-7 w-7 items-center justify-center"
      title={`${pct}%`}
    >
      <svg width="28" height="28" className="-rotate-90" aria-hidden>
        <circle
          cx="14"
          cy="14"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-border"
        />
        <circle
          cx="14"
          cy="14"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="text-primary"
        />
      </svg>
      <span className="absolute text-[8px] font-semibold text-text-secondary">
        {pct}
      </span>
    </span>
  );
}

export default function HeroExtractionPreview() {
  return (
    <div
      aria-hidden
      className="hero-extraction-preview relative mx-auto w-full max-w-[440px]"
    >
      {/* Subtle intelligence grid behind the stack */}
      <div className="hero-doc-grid pointer-events-none absolute inset-0 -z-10 opacity-40" />

      <div className="doc-shape-layered hero-doc-drift pb-6">
        {/* Deep back sheet — financial / secondary document */}
        <div
          className="doc-shape-layer-far doc-shape-corner-clip rounded-[var(--radius-card)] border border-border/30 bg-surface-soft/80"
          style={{ height: "17rem" }}
        />

        {/* Mid back layer — stacked-document effect */}
        <div
          className="doc-shape-layer-back doc-shape-corner-clip rounded-[var(--radius-card)] border border-border/40 bg-surface-soft"
          style={{ height: "18rem" }}
        />

        {/* Mock PDF page with highlighted extraction zones */}
        <div className="doc-shape-layer-front doc-shape-corner-clip rounded-[var(--radius-card)] border border-border bg-surface p-5 shadow-[var(--shadow-elevated)]">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-text-secondary">
              Document.pdf
            </p>
            <span className="rounded-full bg-surface-soft px-2 py-0.5 text-[10px] font-medium text-text-muted">
              Page 1
            </span>
          </div>

          <div className="mt-4 space-y-2">
            <div className="h-2 w-3/5 rounded-full bg-border" />
            <div className="h-1.5 w-4/5 rounded-full bg-border/70" />
            <div className="h-1.5 w-2/3 rounded-full bg-border/70" />
          </div>

          <div className="relative mt-4 rounded-sm border border-primary/30 bg-primary/8 px-3 py-2">
            <ZoneMarker number={1} />
            <p className="text-[10px] font-medium uppercase tracking-wide text-primary/70">
              Contract No.
            </p>
            <p className="mt-0.5 font-mono text-xs text-foreground">
              W912HQ-24-C-0001
            </p>
          </div>

          <div className="relative mt-3 rounded-sm border border-success/30 bg-success/8 px-3 py-2">
            <ZoneMarker number={2} />
            <p className="text-[10px] font-medium uppercase tracking-wide text-success/70">
              Award Date
            </p>
            <p className="mt-0.5 font-mono text-xs text-foreground">
              08/19/2026
            </p>
          </div>

          <div className="relative mt-3 rounded-sm border border-primary/30 bg-primary/8 px-3 py-2">
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

      {/* Thin connector from source stack to results */}
      <svg
        className="pointer-events-none absolute right-[18%] top-[42%] h-16 w-12 text-primary/35"
        viewBox="0 0 48 64"
        fill="none"
        aria-hidden
      >
        <path
          d="M8 4 C 20 20, 28 36, 40 58"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeDasharray="3 3"
        />
        <circle cx="40" cy="58" r="2.5" fill="currentColor" />
      </svg>

      {/* Extracted fields panel — layered on top, offset toward the corner */}
      <div className="hero-results-panel relative -mt-14 ml-auto w-[82%] rounded-[var(--radius-card)] border border-border bg-surface p-4 shadow-[var(--shadow-elevated)]">
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
              <ConfidenceRing confidence={row.confidence} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
