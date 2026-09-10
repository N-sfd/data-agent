"use client";

import type {
  ConfidenceDetail,
  RetrievalTrace,
  ScalarTargetResult,
  ValidationResult,
} from "@/types/document";

function CheckStatusDot({ status }: { status: string }) {
  const color =
    status === "passed"
      ? "bg-success"
      : status === "failed"
        ? "bg-danger"
        : "bg-text-muted";
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${color}`} />;
}

function RetrievalSection({ retrieval }: { retrieval: RetrievalTrace }) {
  const candidates = retrieval.candidate_pages.slice(0, 5);
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
        Retrieval
      </p>
      <p className="mt-1 text-sm text-foreground">
        Selected pages{" "}
        <span className="font-medium">
          {retrieval.selected_pages.length
            ? retrieval.selected_pages.join(", ")
            : "—"}
        </span>
        <span className="text-text-secondary">
          {" "}
          · {retrieval.deterministic_status.replace(/_/g, " ")}
          {retrieval.ai_fallback_required ? " · AI fallback" : ""}
        </span>
      </p>
      {candidates.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 text-xs text-text-secondary">
          {candidates.map((item) => (
            <li key={item.page} className="flex items-center justify-between gap-2">
              <span>Page {item.page}</span>
              <span className="font-mono tabular-nums">{item.score.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ConfidenceSection({ detail }: { detail: ConfidenceDetail }) {
  const signals = detail.signals;
  const rows: Array<[string, string]> = [
    ["Exact label", signals.exact_label_match ? "yes" : "no"],
    ["Label proximity", signals.label_proximity],
    ["Native text", signals.native_text ? "yes" : "no"],
    ["Format valid", signals.format_validation ? "yes" : "no"],
    ["Source grounded", signals.source_grounded ? "yes" : "no"],
    ["Corroborations", String(signals.corroborating_occurrences)],
    ["Ambiguity", signals.ambiguity ? "yes" : "no"],
    ["AI fallback", signals.ai_fallback ? "yes" : "no"],
  ];
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
        Confidence signals
      </p>
      <p className="mt-1 text-sm text-foreground">
        {detail.band} · {detail.score.toFixed(2)}
      </p>
      <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-text-secondary">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-2">
            <dt>{label}</dt>
            <dd className="font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function ValidationSection({ validation }: { validation: ValidationResult }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
        Validation checks
      </p>
      <ul className="mt-1.5 space-y-1 text-sm text-foreground">
        {validation.checks.map((check) => (
          <li key={check.type} className="flex items-center gap-2">
            <CheckStatusDot status={check.status} />
            <span className="capitalize">{check.type.replace(/_/g, " ")}</span>
            <span className="text-xs uppercase text-text-muted">{check.status}</span>
          </li>
        ))}
      </ul>
      {validation.warnings.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 text-xs text-warning">
          {validation.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Inspectable retrieval → confidence → validation for one scalar result. */
export default function IntelligenceTrace({
  scalar,
}: {
  scalar: ScalarTargetResult | null | undefined;
}) {
  if (!scalar) return null;
  const { retrieval, confidence_detail: confidence, validation } = scalar;
  if (!retrieval && !confidence && !validation) return null;

  return (
    <div className="mt-3 space-y-3 border-t border-border pt-3">
      {retrieval && <RetrievalSection retrieval={retrieval} />}
      {confidence && <ConfidenceSection detail={confidence} />}
      {validation && <ValidationSection validation={validation} />}
    </div>
  );
}
