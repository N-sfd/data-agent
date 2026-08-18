"use client";

import { useState } from "react";
import {
  Check,
  CheckCheck,
  Clock,
  ExternalLink,
  FileSearch,
  HelpCircle,
  Pencil,
  X,
} from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import { getFieldAuditLog } from "@/lib/documents";
import type {
  FieldAuditEntry,
  MetadataField,
  ReviewAction,
  ReviewStatus,
} from "@/types/document";

interface ReviewFieldListProps {
  documentId: string;
  fields: MetadataField[];
  activeFieldKey: string | null;
  onSelectField: (field: MetadataField) => void;
  onReviewField: (
    fieldKey: string,
    action: ReviewAction,
    value?: string,
  ) => Promise<void> | void;
  onAcceptAll: () => void;
  reviewingKey: string | null;
  acceptingAll: boolean;
}

const GROUP_ORDER = [
  "Identification",
  "Parties",
  "Dates",
  "Financial",
  "Legal",
  "Commercial",
  "Compliance",
];

const STATUS_STYLES: Record<ReviewStatus, string> = {
  pending: "bg-slate-100 text-slate-600",
  accepted: "bg-emerald-50 text-emerald-700",
  edited: "bg-blue-50 text-blue-700",
  rejected: "bg-red-50 text-red-700",
  unknown: "bg-amber-50 text-amber-700",
};

const STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "Pending",
  accepted: "Accepted",
  edited: "Edited",
  rejected: "Rejected",
  unknown: "Unknown",
};

const ACTION_LABELS: Record<ReviewAction, string> = {
  accept: "Accepted",
  edit: "Edited",
  reject: "Rejected",
  mark_unknown: "Marked Unknown",
};

export default function ReviewFieldList({
  documentId,
  fields,
  activeFieldKey,
  onSelectField,
  onReviewField,
  onAcceptAll,
  reviewingKey,
  acceptingAll,
}: ReviewFieldListProps) {
  const groups = new Map<string, MetadataField[]>();

  for (const field of fields) {
    const existing = groups.get(field.field_group) ?? [];
    existing.push(field);
    groups.set(field.field_group, existing);
  }

  const orderedGroups = [
    ...GROUP_ORDER.filter((group) => groups.has(group)),
    ...[...groups.keys()].filter(
      (group) => !GROUP_ORDER.includes(group),
    ),
  ];

  const allReviewed =
    fields.length > 0 &&
    fields.every((field) => field.review_status !== "pending");

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5">
        <p className="text-sm font-semibold text-slate-900">
          Extracted Data
        </p>

        <button
          type="button"
          onClick={onAcceptAll}
          disabled={acceptingAll || allReviewed}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <CheckCheck className="h-3.5 w-3.5" />
          {allReviewed ? "All reviewed" : "Accept All"}
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full min-w-[640px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2 font-semibold">Field</th>
              <th className="px-4 py-2 font-semibold">
                Extracted Value
              </th>
              <th className="px-4 py-2 font-semibold">Confidence</th>
              <th className="px-4 py-2 font-semibold">Status</th>
              <th className="px-4 py-2 font-semibold">Actions</th>
            </tr>
          </thead>

          <tbody>
            {orderedGroups.map((group) => (
              <FieldGroupRows
                key={group}
                documentId={documentId}
                group={group}
                fields={groups.get(group)!}
                activeFieldKey={activeFieldKey}
                reviewingKey={reviewingKey}
                onSelectField={onSelectField}
                onReviewField={onReviewField}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FieldGroupRows({
  documentId,
  group,
  fields,
  activeFieldKey,
  reviewingKey,
  onSelectField,
  onReviewField,
}: {
  documentId: string;
  group: string;
  fields: MetadataField[];
  activeFieldKey: string | null;
  reviewingKey: string | null;
  onSelectField: (field: MetadataField) => void;
  onReviewField: (
    fieldKey: string,
    action: ReviewAction,
    value?: string,
  ) => Promise<void> | void;
}) {
  return (
    <>
      <tr>
        <th
          colSpan={5}
          className="border-t border-slate-200 bg-slate-100 px-4 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"
        >
          {group}
        </th>
      </tr>

      {fields.map((field) => (
        <FieldRow
          key={field.field_key}
          documentId={documentId}
          field={field}
          active={field.field_key === activeFieldKey}
          busy={reviewingKey === field.field_key}
          onSelect={() => onSelectField(field)}
          onReview={onReviewField}
        />
      ))}
    </>
  );
}

function FieldRow({
  documentId,
  field,
  active,
  busy,
  onSelect,
  onReview,
}: {
  documentId: string;
  field: MetadataField;
  active: boolean;
  busy: boolean;
  onSelect: () => void;
  onReview: (
    fieldKey: string,
    action: ReviewAction,
    value?: string,
  ) => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [draftValue, setDraftValue] = useState(field.value);

  const [showSource, setShowSource] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<
    FieldAuditEntry[] | null
  >(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  async function toggleHistory() {
    if (showHistory) {
      setShowHistory(false);
      return;
    }

    setShowHistory(true);

    if (history === null) {
      setHistoryLoading(true);

      try {
        const entries = await getFieldAuditLog(
          documentId,
          field.field_key,
        );
        setHistory(entries);
      } catch {
        setHistory([]);
      } finally {
        setHistoryLoading(false);
      }
    }
  }

  async function submitEdit() {
    if (!draftValue.trim()) return;

    await onReview(field.field_key, "edit", draftValue.trim());
    setEditing(false);
    setHistory(null);
  }

  return (
    <>
      <tr
        onClick={onSelect}
        className={[
          "cursor-pointer border-t border-slate-200 align-top transition",
          active ? "bg-blue-50" : "bg-white hover:bg-slate-50",
        ].join(" ")}
      >
        <td className="px-4 py-2.5 text-xs text-slate-500">
          {field.label}
        </td>

        <td className="px-4 py-2.5">
          {editing ? (
            <div
              onClick={(event) => event.stopPropagation()}
              className="flex items-center gap-1.5"
            >
              <input
                type="text"
                value={draftValue}
                onChange={(event) =>
                  setDraftValue(event.target.value)
                }
                className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1 text-xs"
                autoFocus
              />

              <button
                type="button"
                onClick={submitEdit}
                disabled={busy}
                className="rounded-md bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Save
              </button>

              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setDraftValue(field.value);
                }}
                className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
          ) : (
            <p className="max-w-xs truncate text-sm font-medium text-slate-800">
              {field.value}
            </p>
          )}
        </td>

        <td className="px-4 py-2.5">
          <ConfidenceBadge confidence={field.confidence} />
        </td>

        <td className="px-4 py-2.5">
          <span
            className={[
              "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
              STATUS_STYLES[field.review_status],
            ].join(" ")}
          >
            {STATUS_LABELS[field.review_status]}
          </span>
        </td>

        <td className="px-4 py-2.5">
          {!editing && (
            <div
              onClick={(event) => event.stopPropagation()}
              className="flex flex-wrap items-center gap-1.5"
            >
              <ActionButton
                icon={<Check className="h-3 w-3" />}
                label="Accept"
                tone="emerald"
                disabled={busy}
                onClick={() => onReview(field.field_key, "accept")}
              />

              <ActionButton
                icon={<Pencil className="h-3 w-3" />}
                label="Edit"
                tone="slate"
                disabled={busy}
                onClick={() => setEditing(true)}
              />

              <ActionButton
                icon={<X className="h-3 w-3" />}
                label="Reject"
                tone="red"
                disabled={busy}
                onClick={() => onReview(field.field_key, "reject")}
              />

              <ActionButton
                icon={<HelpCircle className="h-3 w-3" />}
                label="Mark Unknown"
                tone="amber"
                disabled={busy}
                onClick={() =>
                  onReview(field.field_key, "mark_unknown")
                }
              />

              <button
                type="button"
                onClick={() => setShowSource((current) => !current)}
                className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700"
              >
                <FileSearch className="h-3 w-3" />
                {showSource ? "Hide Source" : "Source"}
              </button>

              <button
                type="button"
                onClick={toggleHistory}
                className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-700"
              >
                <Clock className="h-3 w-3" />
                {showHistory ? "Hide History" : "History"}
              </button>
            </div>
          )}
        </td>
      </tr>

      {showSource && (
        <tr className="border-t border-slate-100 bg-slate-50">
          <td colSpan={5} className="px-4 py-2.5">
            <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-2.5 text-xs">
              <div className="flex flex-wrap items-center gap-3 text-slate-500">
                <span>
                  Page{" "}
                  <span className="font-medium text-slate-800">
                    {field.evidence.page_number}
                  </span>
                </span>

                {field.evidence.section && (
                  <span>
                    Section{" "}
                    <span className="font-medium text-slate-800">
                      {field.evidence.section}
                    </span>
                  </span>
                )}
              </div>

              <p className="rounded-md bg-slate-50 p-2 italic text-slate-700">
                &ldquo;{field.evidence.source_text}&rdquo;
              </p>

              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect();
                }}
                className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:text-blue-800"
              >
                <ExternalLink className="h-3 w-3" />
                Open Source
              </button>
            </div>
          </td>
        </tr>
      )}

      {showHistory && (
        <tr className="border-t border-slate-100 bg-slate-50">
          <td colSpan={5} className="px-4 py-2.5">
            <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-2.5 text-xs">
              <div>
                <span className="text-slate-400">AI extracted</span>
                <p className="font-medium text-slate-800">
                  {field.original_value}
                </p>
              </div>

              {historyLoading && (
                <p className="text-slate-400">Loading history...</p>
              )}

              {!historyLoading &&
                history !== null &&
                history.length === 0 && (
                  <p className="text-slate-400">
                    No reviewer actions yet.
                  </p>
                )}

              {!historyLoading &&
                history?.map((entry, index) => (
                  <div
                    key={index}
                    className="border-t border-slate-100 pt-2"
                  >
                    <span className="text-slate-400">
                      Reviewer{" "}
                      {ACTION_LABELS[entry.action].toLowerCase()}
                      {entry.new_value &&
                      entry.new_value !== entry.previous_value
                        ? ":"
                        : ""}
                    </span>

                    {entry.new_value &&
                      entry.new_value !== entry.previous_value && (
                        <p className="font-medium text-slate-800">
                          {entry.new_value}
                        </p>
                      )}

                    <p className="mt-1 text-slate-500">
                      Changed by: {entry.changed_by}
                    </p>
                    <p className="text-slate-400">
                      {new Date(entry.changed_at).toLocaleString()}
                    </p>
                  </div>
                ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function ActionButton({
  icon,
  label,
  tone,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  tone: "emerald" | "slate" | "red" | "amber";
  disabled: boolean;
  onClick: () => void;
}) {
  const toneClasses = {
    emerald:
      "border-emerald-200 text-emerald-700 hover:bg-emerald-50",
    slate: "border-slate-200 text-slate-600 hover:bg-slate-50",
    red: "border-red-200 text-red-700 hover:bg-red-50",
    amber: "border-amber-200 text-amber-700 hover:bg-amber-50",
  }[tone];

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-60",
        toneClasses,
      ].join(" ")}
    >
      {icon}
      {label}
    </button>
  );
}
