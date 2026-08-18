"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, GitBranch, X } from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import { confirmRelationship } from "@/lib/documents";
import type { ChildRelationship } from "@/types/document";

interface ContractRelationshipsTreeProps {
  rootLabel: string;
  childRelationships: ChildRelationship[];
  onChanged: (updated: ChildRelationship[]) => void;
}

const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  amendment_of: "Amendment",
  change_order_of: "Change Order",
  sow_of: "Statement of Work",
  subcontract_of: "Subcontract",
};

export default function ContractRelationshipsTree({
  rootLabel,
  childRelationships,
  onChanged,
}: ContractRelationshipsTreeProps) {
  const [busyId, setBusyId] = useState<string | null>(null);

  async function resolve(
    child: ChildRelationship,
    action: "confirm" | "reject",
  ) {
    setBusyId(child.child_document_id);

    try {
      const result = await confirmRelationship(
        child.child_document_id,
        action,
      );

      onChanged(
        childRelationships.map((entry) =>
          entry.child_document_id === child.child_document_id
            ? { ...entry, status: result.status }
            : entry,
        ),
      );
    } catch {
      // Non-fatal; the row simply stays actionable for retry.
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-violet-600" />
        <p className="text-xs font-semibold uppercase tracking-wide text-violet-600">
          Contract Relationships
        </p>
      </div>

      <p className="mt-3 truncate text-sm font-semibold text-slate-900">
        {rootLabel}
      </p>

      <div className="mt-2 space-y-2">
        {childRelationships.map((child, index) => {
          const isLast = index === childRelationships.length - 1;
          const connector = isLast ? "└──" : "├──";
          const relationshipLabel =
            RELATIONSHIP_TYPE_LABELS[child.relationship_type] ??
            child.relationship_type;

          return (
            <div
              key={child.child_document_id}
              className="flex flex-wrap items-center gap-2 pl-2 text-sm"
            >
              <span className="font-mono text-slate-300">
                {connector}
              </span>

              <Link
                href={`/documents/${child.child_document_id}/review`}
                className="font-medium text-blue-700 hover:text-blue-800 hover:underline"
              >
                {relationshipLabel}
                {child.child_document_number
                  ? ` — ${child.child_document_number}`
                  : ` — ${child.child_document_title}`}
              </Link>

              <ConfidenceBadge confidence={child.confidence} />

              {child.status === "pending" ? (
                <span className="ml-auto flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => resolve(child, "confirm")}
                    disabled={busyId === child.child_document_id}
                    className="inline-flex items-center gap-1 rounded-md border border-emerald-200 px-2 py-1 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Check className="h-3 w-3" />
                    Confirm
                  </button>

                  <button
                    type="button"
                    onClick={() => resolve(child, "reject")}
                    disabled={busyId === child.child_document_id}
                    className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs font-semibold text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <X className="h-3 w-3" />
                    Reject
                  </button>
                </span>
              ) : (
                <span
                  className={[
                    "ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                    child.status === "confirmed"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-500",
                  ].join(" ")}
                >
                  {child.status}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
