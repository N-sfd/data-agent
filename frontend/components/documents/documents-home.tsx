"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, MoreHorizontal, Plus, Search, X } from "lucide-react";

import { ErrorState, LoadingState } from "@/components/layout/StatusState";
import { deleteDocuments, getDocumentStatusCounts, searchDocuments, startProcessingJob } from "@/lib/documents";
import {
  presentDocument,
  statusMark,
  type OperationalStatus,
} from "@/lib/document-presentation";
import { downloadExport, getStagingProfile } from "@/lib/staging-workbook";
import type { DocumentStatus, DocumentSummary } from "@/types/document";

const PAGE_SIZE = 25;

type Filter = "all" | "review" | "ready" | "failed";

const FILTERS: { id: Filter; label: string; status?: DocumentStatus }[] = [
  { id: "all", label: "All Documents" },
  { id: "review", label: "Needs Review", status: "review_required" },
  { id: "ready", label: "Ready", status: "completed" },
  { id: "failed", label: "Failed", status: "failed" },
];

/** Document types reachable from the Documents menu (staging families). */
export const FAMILY_LABELS: Record<string, string> = {
  invoice: "Invoices",
  academic_transcript: "Transcripts & certificates",
  government_contract: "Contracts",
  far_regulation: "FAR regulations",
  correspondence: "Correspondence",
};

function isFilter(value: string | null): value is Filter {
  return FILTERS.some((item) => item.id === value);
}

const TONE: Record<OperationalStatus, string> = {
  ready: "text-success",
  verified: "text-success",
  review: "text-warning",
  failed: "text-danger",
  processing: "text-text-secondary",
};

function updated(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function DocumentsHome() {
  const router = useRouter();
  const params = useSearchParams();
  const urlFilter = params.get("filter");
  const family = params.get("family") ?? "";
  const [filter, setFilter] = useState<Filter>(isFilter(urlFilter) ? urlFilter : "all");
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [debouncedQuery, setDebouncedQuery] = useState(query.trim());
  const [reloadKey, setReloadKey] = useState(0);
  const [offset, setOffset] = useState(0);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<Record<Filter, number> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<DocumentSummary[] | null>(null);
  const [notice, setNotice] = useState("");

  // Counts and the list both come from the server — refreshed after any
  // deletion or reprocess (reloadKey).
  useEffect(() => {
    let active = true;
    getDocumentStatusCounts(family || undefined)
      .then(({ total, by_status }) => {
        if (!active) return;
        setCounts({
          all: total,
          review: by_status.review_required ?? 0,
          ready: by_status.completed ?? 0,
          failed: by_status.failed ?? 0,
        });
      })
      .catch(() => {
        /* The table error state covers a real outage. */
      });
    return () => {
      active = false;
    };
  }, [family, reloadKey]);

  // The Documents menu links here with ?filter= / ?family=; follow it.
  const [seenFilter, setSeenFilter] = useState(urlFilter);
  if (seenFilter !== urlFilter) {
    setSeenFilter(urlFilter);
    setFilter(isFilter(urlFilter) ? urlFilter : "all");
    setOffset(0);
  }

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let active = true;
    const status = FILTERS.find((item) => item.id === filter)?.status;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const result = await searchDocuments({
          q: debouncedQuery || undefined,
          status,
          family: family || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        if (!active) return;
        setDocuments(result.documents);
        setTotal(result.total);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to load documents.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [filter, debouncedQuery, offset, reloadKey, family]);

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const pageIds = documents.map((document) => document.document_id);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function exportDocument(document: DocumentSummary) {
    setMenuFor(null);
    try {
      const profile = await getStagingProfile(document.document_id);
      const capability = profile.export_capabilities.find((item) => item.format === "xlsx");
      if (!capability) throw new Error("This document has no Excel export.");
      await downloadExport(capability, document.original_filename.replace(/\.[^.]+$/, ""));
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Export failed.");
    }
  }

  async function reprocess(document: DocumentSummary) {
    setMenuFor(null);
    try {
      await startProcessingJob(document.document_id);
      setNotice(`Reprocessing ${document.original_filename}…`);
      setReloadKey((key) => key + 1);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Reprocess failed.");
    }
  }

  async function confirmDelete() {
    if (!confirm) return;
    const ids = confirm.map((document) => document.document_id);
    try {
      const result = await deleteDocuments(ids);
      const refused = result.not_found.length + result.forbidden.length;
      setNotice(
        `${result.deleted.length} document${result.deleted.length === 1 ? "" : "s"} deleted` +
          (refused ? ` · ${refused} could not be deleted (not yours or already gone)` : "") +
          (result.storage_errors.length ? ` · ${result.storage_errors.length} stored file(s) need cleanup` : "") +
          ".",
      );
      setSelected((current) => {
        const next = new Set(current);
        for (const id of result.deleted) next.delete(id);
        return next;
      });
      setConfirm(null);
      setReloadKey((key) => key + 1);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Delete failed.");
      setConfirm(null);
    }
  }

  return (
    <div className="w-full px-4 py-8 sm:px-6" data-testid="documents-home">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            {family ? FAMILY_LABELS[family] ?? "Documents" : "Documents"}
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Every extracted document, with the staging profile Data Agent resolved.
          </p>
          {family && (
            <Link
              href="/documents"
              className="mt-2 inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary-soft px-2.5 py-0.5 text-xs font-medium text-primary hover:border-primary"
              aria-label={`Clear type filter ${FAMILY_LABELS[family] ?? family}`}
            >
              Type: {FAMILY_LABELS[family] ?? family}
              <X className="h-3 w-3" aria-hidden="true" />
            </Link>
          )}
        </div>
        <Link href="/extraction/new" className="btn-hero-primary">
          <Plus className="h-4 w-4" />
          New Document
        </Link>
      </div>

      <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <Metric label="Documents" value={counts?.all} />
        <Metric label="Need Review" value={counts?.review} tone="text-warning" />
        <Metric label="Ready" value={counts?.ready} tone="text-success" />
        <Metric label="Failed" value={counts?.failed} tone="text-danger" />
      </dl>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setOffset(0);
              setQuery(event.target.value);
            }}
            placeholder="Search documents, fields, parties, FAR numbers..."
            className="w-full rounded-xl border border-border bg-surface py-2.5 pl-9 pr-3 text-sm outline-none focus:border-primary/40"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={filter === item.id}
              onClick={() => {
                setOffset(0);
                setFilter(item.id);
              }}
              className={[
                "rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                filter === item.id
                  ? "border border-primary bg-primary text-white"
                  : "border border-border bg-surface text-text-secondary hover:border-primary/40 hover:text-foreground",
              ].join(" ")}
            >
              {item.label}
              <span className={filter === item.id ? "text-white/70" : "text-text-muted"}> {counts ? counts[item.id] : "–"}</span>
            </button>
          ))}
        </div>
      </div>

      {notice && (
        <div className="mt-4 flex items-center justify-between rounded-lg border border-border bg-surface-soft px-3 py-2 text-sm text-text-secondary" role="status">
          {notice}
          <button type="button" onClick={() => setNotice("")} aria-label="Dismiss" className="text-text-muted hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {selected.size > 0 && (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 text-sm" role="region" aria-label="Selection">
          <span className="font-medium text-foreground">{selected.size} selected</span>
          <button
            type="button"
            onClick={() => setConfirm(documents.filter((document) => selected.has(document.document_id)))}
            className="rounded-md border border-danger/40 px-2.5 py-1 text-xs font-medium text-danger hover:bg-danger/5"
          >
            Delete
          </button>
          <button type="button" onClick={() => setSelected(new Set())} className="text-xs text-text-secondary hover:text-foreground">
            Clear selection
          </button>
        </div>
      )}

      {error && (
        <div className="mt-6">
          <ErrorState error={error} onRetry={() => setReloadKey((key) => key + 1)} />
        </div>
      )}

      {/* relative: keeps absolutely positioned (sr-only) labels inside the scroller. */}
      <div className="relative mt-4 overflow-x-auto rounded-xl border border-border bg-surface">
        {loading ? (
          <LoadingState title="Loading documents..." description="Connecting to Data Agent…" />
        ) : documents.length === 0 ? (
          <p className="px-6 py-12 text-center text-sm text-text-secondary">
            No documents match this view.
          </p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] font-medium text-text-muted">
                <th className="w-10 px-3 py-2">
                  <input
                    type="checkbox"
                    aria-label="Select all on this page"
                    checked={allSelected}
                    onChange={() =>
                      setSelected((current) => {
                        const next = new Set(current);
                        for (const id of pageIds) {
                          if (allSelected) next.delete(id);
                          else next.add(id);
                        }
                        return next;
                      })
                    }
                  />
                </th>
                <th className="px-3 py-2">Document</th>
                <th className="px-3 py-2">Type</th>
                <th className="hidden px-3 py-2 sm:table-cell">Profile</th>
                <th className="px-3 py-2">Status</th>
                <th className="hidden px-3 py-2 md:table-cell">Updated</th>
                <th className="w-12 px-3 py-2">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => {
                const row = presentDocument(document);
                const open = () => router.push(`/documents/${document.document_id}`);
                return (
                  <tr
                    key={document.document_id}
                    onClick={open}
                    className="h-11 cursor-pointer border-b border-border/70 last:border-0 hover:bg-surface-soft"
                  >
                    <td className="px-3 py-2" onClick={(event) => event.stopPropagation()}>
                      <input
                        type="checkbox"
                        aria-label={`Select ${document.original_filename}`}
                        checked={selected.has(document.document_id)}
                        onChange={() => toggle(document.document_id)}
                      />
                    </td>
                    <td className="max-w-[28rem] truncate px-3 py-2 font-medium text-foreground" title={document.original_filename}>
                      {document.original_filename}
                    </td>
                    <td className="px-3 py-2 text-text-secondary">{row.typeLabel}</td>
                    <td className={`hidden px-3 py-2 sm:table-cell ${row.staged ? "text-text-secondary" : "text-text-muted"}`}>
                      {row.profileLabel}
                    </td>
                    <td className={`px-3 py-2 font-medium ${TONE[row.status]}`}>
                      {statusMark(row.status)} {row.statusLabel}
                    </td>
                    <td className="hidden px-3 py-2 text-text-secondary tabular-nums md:table-cell">{updated(document.last_updated)}</td>
                    <td className="relative px-3 py-2 text-right" onClick={(event) => event.stopPropagation()}>
                      <button
                        type="button"
                        aria-label={`Actions for ${document.original_filename}`}
                        aria-haspopup="menu"
                        aria-expanded={menuFor === document.document_id}
                        onClick={() => setMenuFor((current) => (current === document.document_id ? null : document.document_id))}
                        className="rounded-md p-1 text-text-secondary hover:bg-surface-soft hover:text-foreground"
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </button>
                      {menuFor === document.document_id && (
                        <RowMenu
                          staged={row.staged}
                          onClose={() => setMenuFor(null)}
                          onOpen={open}
                          onExport={() => void exportDocument(document)}
                          onReprocess={() => void reprocess(document)}
                          onDelete={() => {
                            setMenuFor(null);
                            setConfirm([document]);
                          }}
                        />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-text-secondary">
          <p>
            {from}–{to} of {total.toLocaleString()}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
              className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <button
              type="button"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset((value) => value + PAGE_SIZE)}
              className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {confirm && <DeleteDialog documents={confirm} onCancel={() => setConfirm(null)} onConfirm={confirmDelete} />}
    </div>
  );
}

function RowMenu({
  staged,
  onClose,
  onOpen,
  onExport,
  onReprocess,
  onDelete,
}: {
  staged: boolean;
  onClose: () => void;
  onOpen: () => void;
  onExport: () => void;
  onReprocess: () => void;
  onDelete: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onDocument(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) onClose();
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", onDocument);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocument);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);
  const item = "block w-full px-3 py-1.5 text-left text-sm hover:bg-surface-soft";
  return (
    <div ref={ref} role="menu" className="absolute right-3 top-9 z-30 w-40 rounded-lg border border-border bg-surface py-1 shadow-md">
      <button type="button" role="menuitem" className={item} onClick={onOpen}>
        Open
      </button>
      <button type="button" role="menuitem" className={`${item} disabled:text-text-muted`} onClick={onExport} disabled={!staged}>
        Export
      </button>
      <button type="button" role="menuitem" className={item} onClick={onReprocess}>
        Reprocess
      </button>
      <div className="my-1 border-t border-border" />
      <button type="button" role="menuitem" className={`${item} text-danger`} onClick={onDelete}>
        Delete
      </button>
    </div>
  );
}

function DeleteDialog({
  documents,
  onCancel,
  onConfirm,
}: {
  documents: DocumentSummary[];
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onCancel();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, busy]);
  const many = documents.length > 1;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4" role="dialog" aria-modal="true" aria-labelledby="delete-title">
      <div className="w-full max-w-md rounded-xl border border-border bg-surface p-5 shadow-xl">
        <h2 id="delete-title" className="text-base font-semibold text-foreground">
          {many ? `Delete ${documents.length} documents?` : "Delete document?"}
        </h2>
        <ul className="mt-2 max-h-40 space-y-0.5 overflow-y-auto text-sm font-medium text-foreground">
          {documents.map((document) => (
            <li key={document.document_id} className="truncate">
              {document.original_filename}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm leading-6 text-text-secondary">
          This will permanently delete the source document{many ? "s" : ""}, extracted data, staging data, review
          information, and generated artifacts.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={busy} className="btn-secondary px-3 py-1.5 text-sm">
            Cancel
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              await onConfirm();
              setBusy(false);
            }}
            className="rounded-lg bg-danger px-3 py-1.5 text-sm font-medium text-white hover:bg-danger/90 disabled:opacity-60"
          >
            {busy ? "Deleting…" : many ? `Delete ${documents.length} Documents` : "Delete Document"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone = "text-foreground",
}: {
  label: string;
  value: number | undefined;
  tone?: string;
}) {
  return (
    <div>
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className={`text-lg font-semibold tabular-nums ${tone}`}>{value === undefined ? <span className="text-text-muted">—</span> : value.toLocaleString()}</dd>
    </div>
  );
}
