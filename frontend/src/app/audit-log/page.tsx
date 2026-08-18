"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, ClipboardList } from "lucide-react";

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
  accept: "bg-emerald-50 text-emerald-700",
  edit: "bg-blue-50 text-blue-700",
  reject: "bg-red-50 text-red-700",
  mark_unknown: "bg-amber-50 text-amber-700",
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
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8 flex items-center gap-2">
        <ClipboardList className="h-5 w-5 text-blue-600" />
        <div>
          <p className="text-sm font-semibold text-blue-600">
            Contract Extraction
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">
            Audit Log
          </h1>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading && entries.length === 0 ? (
          <p className="p-10 text-center text-sm text-slate-500">
            Loading...
          </p>
        ) : entries.length === 0 ? (
          <p className="p-10 text-center text-sm text-slate-500">
            No review actions recorded yet.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left font-semibold text-slate-700">
                    Document
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-700">
                    Field
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-700">
                    Action
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-700">
                    Old Value
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-700">
                    New Value
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-700">
                    Changed By
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-700">
                    Timestamp
                  </th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, index) => (
                  <tr
                    key={index}
                    className="border-t border-slate-100 hover:bg-slate-50"
                  >
                    <td className="px-6 py-3">
                      <Link
                        href={`/documents/${entry.document_id}/review`}
                        className="font-medium text-blue-700 hover:text-blue-800"
                      >
                        {entry.document_filename}
                      </Link>
                    </td>
                    <td className="px-6 py-3 text-slate-600">
                      {entry.field_key}
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className={[
                          "rounded-full px-2.5 py-0.5 text-xs font-semibold",
                          ACTION_STYLES[entry.action],
                        ].join(" ")}
                      >
                        {ACTION_LABELS[entry.action]}
                      </span>
                    </td>
                    <td className="max-w-[160px] truncate px-6 py-3 text-slate-500">
                      {entry.previous_value || "—"}
                    </td>
                    <td className="max-w-[160px] truncate px-6 py-3 text-slate-800">
                      {entry.new_value || "—"}
                    </td>
                    <td className="px-6 py-3 text-slate-600">
                      {entry.changed_by}
                    </td>
                    <td className="px-6 py-3 text-slate-500">
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
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
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
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
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
              className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
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
