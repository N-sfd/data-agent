"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight, Loader2 } from "lucide-react";

import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";
import ConfidenceIndicator from "@/components/confidence-indicator";
import {
  aggregateFieldAcrossRepository,
  filterMatchesByValue,
} from "@/lib/field-explorer";
import {
  EXPLORER_FIELDS,
  type ExplorerFieldKey,
  type FieldAggregation,
} from "@/lib/field-schema";

function ExplorerContent() {
  const searchParams = useSearchParams();
  const initialField =
    (searchParams.get("field") as ExplorerFieldKey | null) ?? "payment_terms";
  const initialValue = searchParams.get("value");

  const [selectedField, setSelectedField] = useState<ExplorerFieldKey>(
    EXPLORER_FIELDS.some((f) => f.key === initialField)
      ? initialField
      : "payment_terms",
  );
  const [aggregation, setAggregation] = useState<FieldAggregation | null>(null);
  const [selectedValue, setSelectedValue] = useState<string | null>(
    initialValue,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result = await aggregateFieldAcrossRepository(selectedField);
        if (!active) return;
        setAggregation(result);
        if (initialValue && selectedField === initialField) {
          setSelectedValue(initialValue);
        } else {
          setSelectedValue(null);
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to analyze field data.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [selectedField, initialField, initialValue]);

  const matches =
    aggregation && selectedValue
      ? filterMatchesByValue(aggregation, selectedValue)
      : [];

  const maxCount = aggregation?.buckets[0]?.count ?? 1;

  return (
    <>
      <PageHero
        eyebrow="Intelligence / Field Explorer"
        title={
          <>
            Explore contract intelligence
            <br />
            across your entire repository
          </>
        }
        description="Analyze any extracted field across your repository with cross-contract matching and confidence scoring."
      />

      <ContentSection>
      <div className="max-w-md">
        <label className="mb-2 block text-sm text-text-secondary">Field</label>
        <select
          value={selectedField}
          onChange={(event) =>
            setSelectedField(event.target.value as ExplorerFieldKey)
          }
          className="w-full rounded-2xl border border-border bg-surface px-4 py-3.5 text-[15px] outline-none transition duration-200 focus:border-primary/30 focus:ring-2 focus:ring-primary/10"
        >
          {EXPLORER_FIELDS.map((field) => (
            <option key={field.key} value={field.key}>
              {field.label}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="mt-6 rounded-2xl border border-danger/20 bg-danger/5 p-4 text-sm text-danger">
          {error}
        </div>
      )}

      {loading ? (
        <div className="mt-12 flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 className="h-4 w-4 animate-spin" />
          Extracting contract fields across repository...
        </div>
      ) : aggregation ? (
        <div className="mt-12 grid gap-8 lg:grid-cols-[340px_1fr]">
          <div className="editorial-card p-8">
            <h2 className="text-lg font-medium text-foreground">
              {aggregation.field_label}
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              {aggregation.total_analyzed} contracts analyzed
            </p>
            <div className="mt-6 space-y-3">
              {aggregation.buckets.map((bucket) => {
                const width = Math.max(
                  8,
                  Math.round((bucket.count / maxCount) * 100),
                );
                return (
                  <button
                    key={bucket.value}
                    type="button"
                    onClick={() => setSelectedValue(bucket.value)}
                    className={[
                      "w-full rounded-xl p-4 text-left transition duration-200",
                      selectedValue === bucket.value
                        ? "bg-primary-soft ring-1 ring-primary/20"
                        : "hover:bg-surface-soft",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate font-medium text-foreground">
                        {bucket.value}
                      </span>
                      <span className="shrink-0 text-sm text-text-secondary">
                        {bucket.count} contracts
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-soft">
                      <div
                        className="h-full rounded-full bg-primary/70"
                        style={{ width: `${width}%` }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="editorial-card overflow-hidden">
            {selectedValue ? (
              <>
                <div className="border-b border-border px-8 py-6">
                  <p className="text-xl font-medium text-foreground">
                    {matches.length} matching contracts
                  </p>
                  <p className="mt-1 text-sm text-text-secondary">
                    {aggregation.field_label}: {selectedValue}
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="px-8 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                          Contract
                        </th>
                        <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                          Counterparty
                        </th>
                        <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                          Effective
                        </th>
                        <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                          Expires
                        </th>
                        <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                          Confidence
                        </th>
                        <th className="px-4 py-4" />
                      </tr>
                    </thead>
                    <tbody>
                      {matches.map((row) => (
                        <tr
                          key={row.document_id}
                          className="border-b border-border/70 hover:bg-surface-soft/60"
                        >
                          <td className="px-8 py-5 font-medium">
                            {row.contract_title}
                          </td>
                          <td className="px-4 py-5 text-text-secondary">
                            {row.counterparty ?? "—"}
                          </td>
                          <td className="px-4 py-5 text-text-secondary">
                            {row.effective_date ?? "—"}
                          </td>
                          <td className="px-4 py-5 text-text-secondary">
                            {row.expiration_date ?? "—"}
                          </td>
                          <td className="px-4 py-5">
                            {row.confidence !== null ? (
                              <ConfidenceIndicator confidence={row.confidence} />
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="px-4 py-5">
                            <Link
                              href={`/documents/${row.document_id}/review`}
                              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                            >
                              Open
                              <ChevronRight className="h-3.5 w-3.5" />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center px-8 py-20 text-center">
                <p className="font-medium text-foreground">
                  Select a value to explore matching contracts
                </p>
                <p className="mt-2 max-w-sm text-sm text-text-secondary">
                  Click any distribution row to open the cross-contract results
                  table.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : null}
      </ContentSection>
    </>
  );
}

export default function FieldExplorerPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-24 text-sm text-text-secondary">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading Field Explorer...
        </div>
      }
    >
      <ExplorerContent />
    </Suspense>
  );
}
