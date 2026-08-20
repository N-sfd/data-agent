"use client";

import { useState } from "react";
import { Clock, FileStack, Pencil } from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import {
  getClassificationHistory,
  updateClassification,
} from "@/lib/documents";
import {
  DOCUMENT_TYPE_OPTIONS,
  type ClassificationHistoryEntry,
  type ContractClassification,
  type ContractSide,
} from "@/types/document";

interface DocumentProfileCardProps {
  documentId: string;
  classification: ContractClassification;
  reviewerName: string;
  onClassificationChange: (updated: ContractClassification) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  buy_side: "Buy-side Contract",
  sell_side: "Sell-side Contract",
  unknown: "Unknown",
};

const CONTRACT_SIDE_OPTIONS: { value: ContractSide; label: string }[] = [
  { value: "buy_side", label: "Buy-Side" },
  { value: "sell_side", label: "Sell-Side" },
  { value: "unknown", label: "Unknown" },
];

export default function DocumentProfileCard({
  documentId,
  classification,
  reviewerName,
  onClassificationChange,
}: DocumentProfileCardProps) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [draftType, setDraftType] = useState(
    classification.document_type,
  );
  const [draftSide, setDraftSide] = useState<ContractSide>(
    classification.contract_side,
  );
  const [draftLanguage, setDraftLanguage] = useState(
    classification.language ?? "",
  );

  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<
    ClassificationHistoryEntry[] | null
  >(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  function openEditor() {
    setDraftType(classification.document_type);
    setDraftSide(classification.contract_side);
    setDraftLanguage(classification.language ?? "");
    setError("");
    setEditing(true);
  }

  async function submitEdit() {
    setSaving(true);
    setError("");

    try {
      const updated = await updateClassification(documentId, {
        document_type: draftType,
        contract_side: draftSide,
        language: draftLanguage.trim() || undefined,
        changed_by: reviewerName,
      });

      onClassificationChange(updated);
      setEditing(false);
      setHistory(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to update the classification.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function toggleHistory() {
    if (showHistory) {
      setShowHistory(false);
      return;
    }

    setShowHistory(true);

    if (history === null) {
      setHistoryLoading(true);

      try {
        const entries = await getClassificationHistory(documentId);
        setHistory(entries);
      } catch {
        setHistory([]);
      } finally {
        setHistoryLoading(false);
      }
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileStack className="h-4 w-4 text-blue-600" />
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
            Document Profile
          </p>
        </div>

        {!editing && (
          <button
            type="button"
            onClick={openEditor}
            className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700"
          >
            <Pencil className="h-3 w-3" />
            Edit Classification
          </button>
        )}
      </div>

      {editing ? (
        <div className="mt-4 space-y-3">
          <label className="block text-xs text-slate-500">
            Type
            <select
              value={draftType}
              onChange={(event) => setDraftType(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm text-slate-800"
            >
              {DOCUMENT_TYPE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs text-slate-500">
            Contract Side
            <select
              value={draftSide}
              onChange={(event) =>
                setDraftSide(event.target.value as ContractSide)
              }
              className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm text-slate-800"
            >
              {CONTRACT_SIDE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs text-slate-500">
            Language
            <input
              type="text"
              value={draftLanguage}
              onChange={(event) => setDraftLanguage(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm text-slate-800"
            />
          </label>

          {error && <p className="text-xs text-red-700">{error}</p>}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={submitEdit}
              disabled={saving}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Saving..." : "Save"}
            </button>

            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <Field label="Type" value={classification.document_type} />

          <Field
            label="Category"
            value={
              CATEGORY_LABELS[classification.contract_side] ??
              classification.contract_side
            }
          />

          <Field
            label="Language"
            value={classification.language ?? "Unknown"}
          />

          <Field
            label="Document Status"
            value={classification.document_status}
          />

          <div>
            <span className="text-xs text-slate-400">Confidence</span>
            <div className="mt-1">
              <ConfidenceBadge confidence={classification.confidence} />
            </div>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={toggleHistory}
        className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700"
      >
        <Clock className="h-3 w-3" />
        {showHistory ? "Hide History" : "History"}
      </button>

      {showHistory && (
        <div className="mt-2 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-xs">
          {historyLoading && (
            <p className="text-slate-400">Loading history...</p>
          )}

          {!historyLoading &&
            history !== null &&
            history.length === 0 && (
              <p className="text-slate-400">
                No classification changes yet.
              </p>
            )}

          {!historyLoading &&
            history?.map((entry, index) => (
              <div
                key={index}
                className="border-t border-slate-200 pt-2 first:border-t-0 first:pt-0"
              >
                <span className="text-slate-400">
                  {entry.field_changed} changed
                </span>
                <p className="font-medium text-slate-800">
                  {entry.previous_value ?? "—"} →{" "}
                  {entry.new_value ?? "—"}
                </p>
                <p className="mt-1 text-slate-500">
                  Changed by: {entry.changed_by}
                </p>
                <p className="text-slate-400">
                  {new Date(entry.changed_at).toLocaleString()}
                </p>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs text-slate-400">{label}</span>
      <p className="mt-1 truncate text-sm font-medium text-slate-800">
        {value}
      </p>
    </div>
  );
}
