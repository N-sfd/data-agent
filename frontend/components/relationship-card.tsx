"use client";

import { useState } from "react";
import {
  CheckCircle2,
  GitBranch,
  Search,
  XCircle,
} from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import {
  assignRelationship,
  removeRelationship,
  searchDocuments,
} from "@/lib/documents";
import type {
  DetectedRelationship,
  DocumentSummary,
} from "@/types/document";

interface RelationshipCardProps {
  documentId: string;
  relationship: DetectedRelationship | null;
  reviewerName: string;
  onConfirm: () => void;
  onReject: () => void;
  onRelationshipChange: (
    relationship: DetectedRelationship | null,
  ) => void;
  busy?: boolean;
}

const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  amendment_of: "Amendment of",
  change_order_of: "Change Order of",
  sow_of: "Statement of Work of",
  subcontract_of: "Subcontract of",
};

export default function RelationshipCard({
  documentId,
  relationship,
  reviewerName,
  onConfirm,
  onReject,
  onRelationshipChange,
  busy = false,
}: RelationshipCardProps) {
  const [picking, setPicking] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DocumentSummary[]>([]);
  const [searching, setSearching] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState("");

  async function runSearch(event: React.FormEvent) {
    event.preventDefault();

    if (!query.trim()) return;

    setSearching(true);
    setError("");

    try {
      const result = await searchDocuments({
        q: query.trim(),
        limit: 8,
      });
      setResults(
        result.documents.filter(
          (doc) => doc.document_id !== documentId,
        ),
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Search failed.",
      );
    } finally {
      setSearching(false);
    }
  }

  async function choose(parentId: string) {
    setAssigning(true);
    setError("");

    try {
      const updated = await assignRelationship(
        documentId,
        parentId,
        reviewerName,
      );
      onRelationshipChange(updated);
      setPicking(false);
      setQuery("");
      setResults([]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to assign this relationship.",
      );
    } finally {
      setAssigning(false);
    }
  }

  async function remove() {
    setAssigning(true);
    setError("");

    try {
      await removeRelationship(documentId, reviewerName);
      onRelationshipChange(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to remove this relationship.",
      );
    } finally {
      setAssigning(false);
    }
  }

  const picker = picking && (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <form onSubmit={runSearch} className="flex items-center gap-2">
        <Search className="h-3.5 w-3.5 shrink-0 text-slate-400" />
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search for a parent document..."
          autoFocus
          className="w-full min-w-0 rounded-md border border-slate-300 px-2 py-1 text-xs"
        />
        <button
          type="submit"
          disabled={searching}
          className="shrink-0 rounded-md bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {searching ? "..." : "Search"}
        </button>
      </form>

      {results.length > 0 && (
        <div className="mt-2 max-h-48 space-y-1 overflow-y-auto">
          {results.map((doc) => (
            <button
              key={doc.document_id}
              type="button"
              onClick={() => choose(doc.document_id)}
              disabled={assigning}
              className="block w-full truncate rounded-md px-2 py-1.5 text-left text-xs text-slate-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {doc.original_filename}
            </button>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={() => {
          setPicking(false);
          setResults([]);
          setError("");
        }}
        className="mt-2 text-xs text-slate-500 hover:text-slate-700"
      >
        Cancel
      </button>
    </div>
  );

  if (!relationship) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-violet-600" />
          <p className="text-xs font-semibold uppercase tracking-wide text-violet-600">
            Parent Relationship
          </p>
        </div>

        <p className="mt-3 text-sm text-slate-500">
          No parent contract detected for this document.
        </p>

        {!picking && (
          <button
            type="button"
            onClick={() => setPicking(true)}
            className="mt-3 text-xs font-semibold text-blue-700 hover:text-blue-800"
          >
            + Add Relationship
          </button>
        )}

        {picker}

        {error && (
          <p className="mt-2 text-xs text-red-700">{error}</p>
        )}
      </div>
    );
  }

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

      {relationship.reasons.length > 0 && (
        <div className="mt-3 rounded-xl bg-slate-50 p-3">
          <span className="text-xs text-slate-400">Reasons</span>
          <ul className="mt-1.5 space-y-1">
            {relationship.reasons.map((reason) => (
              <li
                key={reason}
                className="flex items-center gap-1.5 text-sm text-slate-700"
              >
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {relationship.status === "pending" ? (
        <div className="mt-5 flex flex-wrap gap-2">
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
            onClick={() => setPicking(true)}
            disabled={busy}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Choose Different Parent
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
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <p
            className={[
              "inline-flex items-center gap-1.5 text-sm font-medium",
              relationship.status === "rejected"
                ? "text-slate-500"
                : "text-emerald-700",
            ].join(" ")}
          >
            {relationship.status === "rejected" ? (
              <XCircle className="h-4 w-4" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            {relationship.status === "confirmed" &&
              "Relationship confirmed"}
            {relationship.status === "manual" &&
              "Relationship manually assigned"}
            {relationship.status === "rejected" &&
              "Relationship rejected"}
          </p>

          {relationship.status !== "rejected" && (
            <>
              <button
                type="button"
                onClick={() => setPicking(true)}
                disabled={assigning}
                className="text-xs font-semibold text-blue-700 hover:text-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Choose Different Parent
              </button>

              <button
                type="button"
                onClick={remove}
                disabled={assigning}
                className="text-xs font-semibold text-red-700 hover:text-red-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Remove Relationship
              </button>
            </>
          )}
        </div>
      )}

      {picker}

      {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
    </div>
  );
}
