import { CheckCircle2, GitBranch, XCircle } from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import type { DetectedRelationship } from "@/types/document";

interface RelationshipCardProps {
  relationship: DetectedRelationship;
  onConfirm: () => void;
  onReject: () => void;
  busy?: boolean;
}

const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  amendment_of: "Amendment of",
  change_order_of: "Change Order of",
  sow_of: "Statement of Work of",
  subcontract_of: "Subcontract of",
};

export default function RelationshipCard({
  relationship,
  onConfirm,
  onReject,
  busy = false,
}: RelationshipCardProps) {
  const relationshipLabel =
    RELATIONSHIP_TYPE_LABELS[relationship.relationship_type] ??
    relationship.relationship_type;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-violet-50">
          <GitBranch className="h-6 w-6 text-violet-600" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-violet-600">
            Detected Relationship
          </p>

          <div className="mt-1 flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-950">
              {relationshipLabel}
            </h2>

            <ConfidenceBadge confidence={relationship.confidence} />
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-slate-50 p-3">
          <span className="text-xs text-slate-400">
            Parent Contract
          </span>

          <p className="mt-1 truncate text-sm font-medium text-slate-800">
            {relationship.parent_document_title}
          </p>

          {relationship.parent_document_number && (
            <p className="mt-0.5 truncate text-xs text-slate-500">
              {relationship.parent_document_number}
            </p>
          )}
        </div>

        <div className="rounded-xl bg-slate-50 p-3">
          <span className="text-xs text-slate-400">Matched On</span>

          <p className="mt-1 text-sm font-medium text-slate-800">
            {relationship.matched_on === "contract_number"
              ? "Contract Number"
              : "Contract Title"}
          </p>
        </div>
      </div>

      {relationship.status === "pending" ? (
        <div className="mt-5 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <CheckCircle2 className="h-4 w-4" />
            Confirm Relationship
          </button>

          <button
            type="button"
            onClick={onReject}
            disabled={busy}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <XCircle className="h-4 w-4" />
            Reject
          </button>
        </div>
      ) : (
        <p
          className={[
            "mt-5 inline-flex items-center gap-1.5 text-sm font-medium",
            relationship.status === "confirmed"
              ? "text-emerald-700"
              : "text-slate-500",
          ].join(" ")}
        >
          {relationship.status === "confirmed" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <XCircle className="h-4 w-4" />
          )}
          {relationship.status === "confirmed"
            ? "Relationship confirmed"
            : "Relationship rejected"}
        </p>
      )}
    </div>
  );
}
