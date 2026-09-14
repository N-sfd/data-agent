"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Trash2, X } from "lucide-react";

import ConfidenceIndicator from "@/components/confidence-indicator";
import DeleteConfirmModal from "@/components/delete-confirm-modal";
import DocumentTypeBadge from "@/components/document-type-badge";
import EmptyState from "@/components/illustrations/empty-state";
import StatusBadge from "@/components/status-badge";
import { getDocumentTypeAppearance } from "@/lib/document-type-icon";
import { formatRelativeTime } from "@/lib/format";
import { deleteDocument } from "@/lib/documents";
import type { DocumentSummary } from "@/types/document";

// Keep bulk-delete bursts modest — deletes are lighter than OCR/analysis
// calls, but the backend is still a single Render free-tier worker.
const MAX_CONCURRENT_DELETES = 3;

function contractTitle(document: DocumentSummary): string {
  return document.original_filename.replace(/\.[^.]+$/, "");
}

type PendingDelete =
  | { kind: "single"; document: DocumentSummary }
  | { kind: "bulk"; documents: DocumentSummary[] };

interface DocumentResultsTableProps {
  documents: DocumentSummary[];
  emptyMessage: string;
  showExtendedColumns?: boolean;
  repositoryMode?: boolean;
  dashboardMode?: boolean;
  onDeleted?: (documentIds: string[]) => void;
}

export default function DocumentResultsTable({
  documents,
  emptyMessage,
  showExtendedColumns = false,
  repositoryMode = false,
  dashboardMode = false,
  onDeleted,
}: DocumentResultsTableProps) {
  const router = useRouter();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(
    null,
  );
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const fullRepository = repositoryMode && !dashboardMode;

  const selectedCount = selectedIds.size;
  const allVisibleSelected =
    documents.length > 0 && documents.every((d) => selectedIds.has(d.document_id));
  const someVisibleSelected = documents.some((d) => selectedIds.has(d.document_id));

  const selectedDocuments = useMemo(
    () => documents.filter((d) => selectedIds.has(d.document_id)),
    [documents, selectedIds],
  );

  function toggleOne(documentId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(documentId)) {
        next.delete(documentId);
      } else {
        next.add(documentId);
      }
      return next;
    });
  }

  function toggleAllVisible() {
    setSelectedIds((current) => {
      if (allVisibleSelected) {
        const next = new Set(current);
        documents.forEach((d) => next.delete(d.document_id));
        return next;
      }
      const next = new Set(current);
      documents.forEach((d) => next.add(d.document_id));
      return next;
    });
  }

  async function runDelete(targets: DocumentSummary[]) {
    setDeleting(true);
    setDeleteError("");

    const succeeded: string[] = [];
    const failed: { name: string; message: string }[] = [];
    let nextIndex = 0;

    async function worker() {
      while (nextIndex < targets.length) {
        const current = targets[nextIndex];
        nextIndex += 1;
        try {
          await deleteDocument(current.document_id);
          succeeded.push(current.document_id);
        } catch (err) {
          failed.push({
            name: current.original_filename,
            message: err instanceof Error ? err.message : "Unknown error",
          });
        }
      }
    }

    await Promise.all(
      Array.from(
        { length: Math.min(MAX_CONCURRENT_DELETES, targets.length) },
        worker,
      ),
    );

    if (succeeded.length > 0) {
      setSelectedIds((current) => {
        const next = new Set(current);
        succeeded.forEach((id) => next.delete(id));
        return next;
      });
      onDeleted?.(succeeded);
    }

    if (failed.length > 0) {
      setDeleteError(
        failed.length === 1
          ? `Couldn't delete "${failed[0].name}": ${failed[0].message}`
          : `Couldn't delete ${failed.length} document(s): ${failed
              .map((f) => f.name)
              .join(", ")}`,
      );
    }

    setDeleting(false);
    setPendingDelete(null);
  }

  if (documents.length === 0) {
    return (
      <EmptyState
        variant="documents"
        description={emptyMessage}
      />
    );
  }

  return (
    <div>
      {fullRepository && selectedCount > 0 && (
        <div className="flex items-center justify-between gap-4 border-b border-border bg-surface-soft/60 px-6 py-3">
          <p className="text-sm font-medium text-foreground">
            {selectedCount} selected
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSelectedIds(new Set())}
              className="text-sm text-text-secondary transition hover:text-foreground"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={() =>
                setPendingDelete({ kind: "bulk", documents: selectedDocuments })
              }
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-danger transition hover:bg-danger/10"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </div>
        </div>
      )}

      {deleteError && (
        <div className="flex items-start justify-between gap-3 border-b border-danger/20 bg-danger/5 px-6 py-3 text-sm text-danger">
          <p>{deleteError}</p>
          <button
            type="button"
            onClick={() => setDeleteError("")}
            aria-label="Dismiss"
            className="shrink-0 rounded p-0.5 hover:bg-danger/10"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-border">
              {fullRepository && (
                <th className="w-10 px-4 py-4">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    ref={(el) => {
                      if (el) {
                        el.indeterminate =
                          someVisibleSelected && !allVisibleSelected;
                      }
                    }}
                    onChange={toggleAllVisible}
                    aria-label="Select all documents on this page"
                    className="h-4 w-4 rounded border-border accent-primary"
                  />
                </th>
              )}
              <th className="px-8 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                Document
              </th>
              {fullRepository && (
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Party
                </th>
              )}
              <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                Type
              </th>
              {fullRepository && (
                <>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                    Effective
                  </th>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                    Expires
                  </th>
                  <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                    Value
                  </th>
                </>
              )}
              <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                Confidence
              </th>
              {(fullRepository || dashboardMode) && (
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  {fullRepository ? "Review" : "Status"}
                </th>
              )}
              {fullRepository && (
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Relationship
                </th>
              )}
              {(fullRepository || dashboardMode) && (
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Source
                </th>
              )}
              {!dashboardMode && showExtendedColumns && !fullRepository && (
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Status
                </th>
              )}
              <th className="px-8 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                Updated
              </th>
              {fullRepository && (
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  <span className="sr-only">Actions</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => {
              const appearance = getDocumentTypeAppearance(
                document.original_filename,
                document.document_type,
              );
              const TypeIcon = appearance.Icon;
              const isSelected = selectedIds.has(document.document_id);
              const isRowDeleting =
                deleting &&
                pendingDelete !== null &&
                (pendingDelete.kind === "single"
                  ? pendingDelete.document.document_id === document.document_id
                  : pendingDelete.documents.some(
                      (d) => d.document_id === document.document_id,
                    ));

              return (
                <tr
                  key={document.document_id}
                  onClick={() =>
                    router.push(
                      `/extraction/new?documentId=${document.document_id}`,
                    )
                  }
                  className={[
                    "cursor-pointer border-b border-border/60 transition duration-200 last:border-0 table-row-hover",
                    isSelected ? "bg-primary/5" : "",
                  ].join(" ")}
                >
                  {fullRepository && (
                    <td
                      className="px-4 py-5"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleOne(document.document_id)}
                        aria-label={`Select ${document.original_filename}`}
                        className="h-4 w-4 rounded border-border accent-primary"
                      />
                    </td>
                  )}
                  <td className="px-8 py-[18px]">
                    <div className="flex items-start gap-3">
                      <span
                        className={[
                          "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border/70",
                          appearance.bgClass,
                        ].join(" ")}
                        title={appearance.label}
                      >
                        <TypeIcon
                          className={["h-4 w-4", appearance.iconClass].join(" ")}
                          strokeWidth={1.75}
                        />
                      </span>
                      <div className="min-w-0">
                        <p className="text-[15px] font-medium text-foreground">
                          {document.document_type ?? contractTitle(document)}
                        </p>
                        <p className="mt-0.5 text-sm text-text-secondary">
                          {document.original_filename}
                        </p>
                      </div>
                    </div>
                  </td>
                  {fullRepository && (
                    <td className="px-5 py-[18px] text-sm text-text-secondary">
                      {document.counterparty ?? "—"}
                    </td>
                  )}
                  <td className="px-4 py-5">
                    <DocumentTypeBadge documentType={document.document_type} size="sm" />
                  </td>
                  {fullRepository && (
                    <>
                      <td className="px-5 py-[18px] text-sm text-text-secondary">
                        {document.effective_date ?? "—"}
                      </td>
                      <td className="px-5 py-[18px] text-sm text-text-secondary">
                        {document.expiration_date ?? "—"}
                      </td>
                      <td className="px-5 py-[18px] text-sm text-text-secondary">
                        {document.contract_value ?? "—"}
                      </td>
                    </>
                  )}
                  <td className="px-4 py-5">
                    {document.confidence !== null ? (
                      <ConfidenceIndicator confidence={document.confidence} />
                    ) : (
                      "—"
                    )}
                  </td>
                  {fullRepository && (
                    <td className="px-5 py-[18px]">
                      <StatusBadge
                        kind="repository"
                        status={document.repository_status ?? "not_approved"}
                      />
                    </td>
                  )}
                  {dashboardMode && (
                    <td className="px-5 py-[18px]">
                      <StatusBadge kind="document" status={document.status} />
                    </td>
                  )}
                  {fullRepository && (
                    <td className="px-5 py-[18px] text-sm text-text-secondary">
                      {document.relationship ?? "—"}
                    </td>
                  )}
                  {(fullRepository || dashboardMode) && (
                    <td className="px-5 py-[18px] text-sm">
                      {document.source_status === "missing" ? (
                        <span
                          className="font-medium text-warning"
                          title="Original PDF is missing — re-upload required for Source Verification"
                        >
                          ⚠ Missing — Re-upload required
                        </span>
                      ) : (
                        <span className="font-medium text-success">
                          ✓ Available
                        </span>
                      )}
                    </td>
                  )}
                  {!dashboardMode && showExtendedColumns && !fullRepository && (
                    <td className="px-5 py-[18px]">
                      <StatusBadge kind="document" status={document.status} />
                    </td>
                  )}
                  <td className="px-8 py-5 text-sm text-text-secondary">
                    {formatRelativeTime(document.last_updated)}
                  </td>
                  {fullRepository && (
                    <td
                      className="px-4 py-5"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setPendingDelete({ kind: "single", document })
                        }
                        disabled={isRowDeleting}
                        title="Delete document"
                        aria-label={`Delete ${document.original_filename}`}
                        className="rounded-lg p-2 text-text-secondary transition duration-200 hover:bg-danger/10 hover:text-danger disabled:opacity-40"
                      >
                        {isRowDeleting ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {pendingDelete && (
        <DeleteConfirmModal
          title={
            pendingDelete.kind === "single"
              ? `Delete "${pendingDelete.document.original_filename}"?`
              : `Delete ${pendingDelete.documents.length} documents?`
          }
          description="This permanently removes the document, its extracted data, and cannot be undone."
          confirmLabel={
            pendingDelete.kind === "bulk"
              ? `Delete ${pendingDelete.documents.length}`
              : "Delete"
          }
          busy={deleting}
          onCancel={() => setPendingDelete(null)}
          onConfirm={() =>
            runDelete(
              pendingDelete.kind === "single"
                ? [pendingDelete.document]
                : pendingDelete.documents,
            )
          }
        />
      )}
    </div>
  );
}
