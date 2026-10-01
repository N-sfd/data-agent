"use client";

import { AlertOctagon, AlertTriangle, Info } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { ErrorState, LoadingState } from "@/components/layout/StatusState";
import { getPortfolio, type NamedCount, type Portfolio, type RiskSeverity } from "@/lib/portfolio";

/** Loads the portfolio once for a page and renders its loading/error states. */
export function usePortfolio(): { portfolio: Portfolio | null; error: string; retry: () => void } {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let active = true;
    getPortfolio()
      .then((data) => active && setPortfolio(data))
      .catch((err: unknown) => active && setError(err instanceof Error ? err.message : "Unable to load portfolio data."));
    return () => {
      active = false;
    };
  }, [tick]);
  const retry = () => {
    setError("");
    setTick((value) => value + 1);
  };
  return { portfolio, error, retry };
}

export function PortfolioGate({
  portfolio,
  error,
  retry,
  children,
}: {
  portfolio: Portfolio | null;
  error: string;
  retry: () => void;
  children: (portfolio: Portfolio) => ReactNode;
}) {
  if (error) return <ErrorState error={error} onRetry={retry} />;
  if (!portfolio) return <LoadingState title="Loading portfolio..." description="Aggregating your documents…" />;
  return <>{children(portfolio)}</>;
}

export function StatTile({ label, value, hint, href }: { label: string; value: string; hint?: string; href?: string }) {
  const body = (
    <>
      <p className="text-2xl font-semibold tabular-nums tracking-tight text-foreground">{value}</p>
      <p className="mt-1 text-sm text-text-secondary">{label}</p>
      {hint && <p className="mt-0.5 text-xs text-text-muted">{hint}</p>}
    </>
  );
  const className = "rounded-xl border border-border bg-surface px-5 py-4";
  return href ? (
    <Link href={href} className={`${className} transition-colors hover:border-primary/40`}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

export function Panel({ title, description, children, action }: { title: string; description?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-surface p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-text-secondary">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="rounded-lg bg-surface-soft px-3 py-6 text-center text-sm text-text-secondary">{children}</p>;
}

/** Magnitude as horizontal bars: one hue, values in text ink, rounded
 * data end, recessive track. Each row is its own table-like line, so the
 * numbers are readable without the bars. */
export function BarList({ items, unit, hrefFor }: { items: NamedCount[]; unit?: string; hrefFor?: (item: NamedCount) => string | null }) {
  if (items.length === 0) return <EmptyNote>No data yet.</EmptyNote>;
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <ul className="space-y-2.5" role="list">
      {items.map((item) => {
        const share = (item.count / max) * 100;
        const href = hrefFor?.(item) ?? null;
        const label = (
          <span className="min-w-0 truncate text-sm text-foreground" title={item.name}>
            {item.name}
          </span>
        );
        return (
          <li key={item.name} className="group" title={`${item.name}: ${item.count.toLocaleString()}${unit ? ` ${unit}` : ""}`}>
            <div className="mb-1 flex items-baseline justify-between gap-3">
              {href ? (
                <Link href={href} className="min-w-0 truncate hover:text-primary">
                  {label}
                </Link>
              ) : (
                label
              )}
              <span className="shrink-0 text-sm tabular-nums text-text-secondary">{item.count.toLocaleString()}</span>
            </div>
            <div className="h-1.5 rounded-full bg-surface-soft">
              <div className="h-1.5 rounded-full bg-primary transition-opacity group-hover:opacity-80" style={{ width: `${Math.max(share, 1.5)}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Uploads per month: single-series vertical bars on one axis with a
 * hover tooltip per bar and the value above the tallest. */
export function MonthBars({ data }: { data: { month: string; count: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (data.length === 0) return <EmptyNote>No uploads yet.</EmptyNote>;
  const max = Math.max(...data.map((item) => item.count), 1);
  const peak = data.findIndex((item) => item.count === max);
  return (
    <div>
      <div className="relative mt-7 flex h-40 items-end justify-center gap-1.5 border-b border-border" role="img" aria-label="Uploads per month">
        {data.map((item, index) => {
          const [year, month] = item.month.split("-");
          const label = `${MONTHS[Number(month) - 1]} ${year}`;
          return (
            <div
              key={item.month}
              className="relative flex h-full max-w-14 flex-1 items-end"
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
            >
              {(hover === index || (hover === null && index === peak)) && (
                <span className="pointer-events-none absolute bottom-full left-1/2 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-surface px-2 py-0.5 text-xs tabular-nums text-foreground shadow-sm">
                  {hover === index ? `${label}: ` : ""}
                  {item.count.toLocaleString()}
                </span>
              )}
              <div
                className={`w-full rounded-t-[4px] bg-primary ${hover !== null && hover !== index ? "opacity-50" : ""}`}
                style={{ height: `${Math.max((item.count / max) * 100, item.count ? 2 : 0)}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex justify-center gap-1.5">
        {data.map((item) => (
          <span key={item.month} className="max-w-14 flex-1 truncate text-center text-[10px] text-text-muted">
            {MONTHS[Number(item.month.split("-")[1]) - 1]}
          </span>
        ))}
      </div>
    </div>
  );
}

const SEVERITY: Record<RiskSeverity, { label: string; tone: string; icon: typeof AlertOctagon }> = {
  high: { label: "High", tone: "bg-danger/10 text-danger", icon: AlertOctagon },
  medium: { label: "Medium", tone: "bg-warning/10 text-warning", icon: AlertTriangle },
  low: { label: "Low", tone: "bg-surface-soft text-text-secondary", icon: Info },
};

/** Status is never color alone: icon + label. */
export function SeverityBadge({ severity }: { severity: RiskSeverity }) {
  const { label, tone, icon: Icon } = SEVERITY[severity];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  );
}

export function percent(value: number | null, digits = 0): string {
  return value == null ? "—" : `${(value * 100).toFixed(digits)}%`;
}
