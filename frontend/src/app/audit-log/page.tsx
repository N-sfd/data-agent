"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

import EmptyState from "@/components/illustrations/empty-state";
import { LoadingState } from "@/components/layout/StatusState";
import PageHeader from "@/components/page-header";
import { getGlobalAuditLog } from "@/lib/documents";
import type { GlobalAuditEntry, ReviewAction } from "@/types/document";

const PAGE_SIZE = 50;

const ACTION_LABELS: Record<ReviewAction, string> = {
  accept: "Accepted",
  edit: "Edited",
  reject: "Rejected",
  mark_unknown: "Marked Unknown",
};

const ACTION_STYLES: Record<ReviewAction, string> = {
  accept: "bg-success/10 text-success",
  edit: "bg-primary-soft text-primary",
  reject: "bg-danger/10 text-danger",
  mark_unknown: "bg-warning/10 text-warning",
};

export default function AuditLogPage() {
  const [entries, setEntries] = useState<GlobalAuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result = await getGlobalAuditLog(PAGE_SIZE, offset);

        if (!active) return;

        setEntries(result.entries);
        setTotal(result.total);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load the audit log.",
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    load();

    return () => {
      active = false;
    };
  }, [offset]);

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="page-container-wide">
      <PageHeader
        title="Audit Log"
        description="Review every human action across extraction, classification, and field review."
      />

      {error && (
        <div className="mb-6 rounded-2xl border border-danger/20 bg-danger/5 p-4 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="editorial-card overflow-hidden">
        {loading && entries.length === 0 ? (
          <LoadingState
            title="Loading audit history..."
            description="Querying provenance logs, human verification stamps, and field modification records."
          />
        ) : entries.length === 0 ? (
          <EmptyState
            variant="documents"
            title="No audit actions recorded yet"
            description="Human review activities, field edits, and extraction acceptance events will appear here with full provenance timestamps."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-8 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                    User
                  </th>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                    Action
                  </th>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                    Document
                  </th>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                    Field
                  </th>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                    Old Value
                  </th>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                    New Value
                  </th>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase text-text-secondary">
                    Timestamp
                  </th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, index) => (
                  <tr
                    key={index}
                    className="border-b border-border/70 hover:bg-surface-soft/60 transition duration-200"
                  >
                    <td className="px-8 py-4 text-foreground">
                      {entry.changed_by}
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={[
                          "rounded-full px-2.5 py-0.5 text-xs font-medium",
                          ACTION_STYLES[entry.action],
                        ].join(" ")}
                      >
                        {ACTION_LABELS[entry.action]}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <Link
                        href={`/documents/${entry.document_id}/review`}
                        className="font-medium text-primary hover:underline"
                      >
                        {entry.document_filename}
                      </Link>
                    </td>
                    <td className="px-4 py-4 text-text-secondary">
                      {entry.field_key}
                    </td>
                    <td className="max-w-[160px] truncate px-4 py-4 text-text-secondary">
                      {entry.previous_value || "—"}
                    </td>
                    <td className="max-w-[160px] truncate px-4 py-4 text-foreground">
                      {entry.new_value || "—"}
                    </td>
                    <td className="px-4 py-4 text-text-secondary">
                      {new Date(entry.changed_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {total > 0 && (
        <div className="mt-6 flex items-center justify-between text-sm text-text-secondary">
          <p>
            Showing {from}–{to} of {total.toLocaleString()}
          </p>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() =>
                setOffset((current) => Math.max(0, current - PAGE_SIZE))
              }
              disabled={offset === 0}
              className="btn-secondary py-1.5 text-xs disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>

            <button
              type="button"
              onClick={() =>
                setOffset((current) => current + PAGE_SIZE)
              }
              disabled={offset + PAGE_SIZE >= total}
              className="btn-secondary py-1.5 text-xs disabled:opacity-40"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
