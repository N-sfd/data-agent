"use client";

import { FileSearch, Search } from "lucide-react";
import { useMemo, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import EvidenceDrawer, { type EvidenceTarget } from "@/components/staging/evidence-drawer";
import { cellSourceRequest, formatCellValue } from "@/components/staging/review-status";
import StagingDatasetTable from "@/components/staging/staging-dataset-table";
import StagingFieldList from "@/components/staging/staging-field-list";
import StagingRecordDrawer from "@/components/staging/staging-record-drawer";
import {
  composePresentation,
  isBlank,
  type FieldItem,
  type PresentationGroup,
  type PresentationSection,
} from "@/lib/presentation-manifest";
import type { StagingCell, StagingColumn, StagingRecord, StagingWorkbook } from "@/lib/staging-workbook";

interface WorkspaceProps {
  workbook: StagingWorkbook;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
  /** Fallback when there is no source panel: show the value in the Source view. */
  onViewInDocument?: (target: EvidenceTarget) => void;
}

/** The business-facing workspace: what information is in this document.
 * How it was extracted lives behind Details (the evidence drawer) and the
 * collapsed technical view. */
export default function PresentationWorkspace({ workbook, documentId, onOpenSource, onViewInDocument }: WorkspaceProps) {
  const manifest = useMemo(() => composePresentation(workbook), [workbook]);
  const [active, setActive] = useState(manifest.groups[0]?.id ?? "");
  const [target, setTarget] = useState<EvidenceTarget | null>(null);
  const current = manifest.groups.find((group) => group.id === active) ?? manifest.groups[0];

  const viewInDocument = (evidence: EvidenceTarget) => {
    setTarget(null);
    const request = cellSourceRequest(evidence.cell, `${evidence.fieldId ?? evidence.cell.canonical_field}:${Date.now()}`);
    if (onOpenSource && request) onOpenSource({ ...request, label: evidence.field });
    else onViewInDocument?.(evidence);
  };

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold tracking-tight text-foreground">{manifest.heading}</h3>
        {manifest.subtitle && <p className="mt-0.5 text-sm text-text-secondary">{manifest.subtitle}</p>}
      </div>

      {manifest.groups.length > 0 && (
        <div role="tablist" aria-label="Document sections" className="flex flex-wrap gap-1.5">
          {manifest.groups.map((group) => {
            const selected = current?.id === group.id;
            return (
              <button
                key={group.id}
                type="button"
                role="tab"
                aria-label={group.label}
                aria-selected={selected}
                onClick={() => setActive(group.id)}
                className={[
                  "rounded-full border px-3 py-1 text-[13px] font-medium transition-colors",
                  selected
                    ? "border-primary bg-primary text-white"
                    : "border-border bg-surface text-text-secondary hover:border-primary/40 hover:text-foreground",
                ].join(" ")}
              >
                {group.label}
              </button>
            );
          })}
        </div>
      )}

      {current ? (
        <GroupBody group={current} documentId={documentId} onSelect={setTarget} onOpenSource={onOpenSource} />
      ) : (
        <p className="rounded-xl border border-border bg-surface-soft px-4 py-8 text-center text-sm text-text-secondary">
          No business information was found in this document. Use Source to inspect the file.
        </p>
      )}

      <TechnicalView workbook={workbook} documentId={documentId} onOpenSource={onOpenSource} />

      {target && (
        <EvidenceDrawer
          target={target}
          onClose={() => setTarget(null)}
          onViewInDocument={onOpenSource || onViewInDocument ? viewInDocument : undefined}
        />
      )}
    </div>
  );
}

function GroupBody({
  group,
  documentId,
  onSelect,
  onOpenSource,
}: {
  group: PresentationGroup;
  documentId: string;
  onSelect: (target: EvidenceTarget) => void;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  return (
    <div className="space-y-6">
      {group.sections.map((section) => (
        <section key={section.id} aria-label={section.title ?? group.label} className="space-y-2">
          {section.title && (
            <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-text-secondary">{section.title}</h4>
          )}
          {section.pattern === "grid" ? (
            <RecordGrid section={section} groupLabel={group.label} documentId={documentId} onSelect={onSelect} onOpenSource={onOpenSource} />
          ) : section.pattern === "summary" ? (
            <SummaryBlock items={section.items} onSelect={onSelect} />
          ) : (
            <DetailList items={section.items} onSelect={onSelect} />
          )}
        </section>
      ))}
    </div>
  );
}

function itemTarget(item: FieldItem): EvidenceTarget {
  return {
    context: item.context,
    field: item.label,
    cell: item.cell,
    sourceLabel: item.sourceLabel,
    fieldId: item.fieldId,
    fragments: item.fragments,
  };
}

/** Compact review indicator; the reason is in Details. */
function ReviewMark({ cell, onOpen }: { cell: StagingCell; onOpen: () => void }) {
  if (cell.review_status !== "Needs Review") return null;
  return (
    <button
      type="button"
      onClick={onOpen}
      className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full bg-warning/10 px-2 py-0.5 text-[11px] font-medium text-warning hover:bg-warning/20"
      title={cell.review_reasons[0] ?? "Check against the original"}
    >
      <span aria-hidden="true">!</span> Needs Review
    </button>
  );
}

/** A value reads as ordinary text; it opens its evidence on click. The
 * hover/focus state and a small evidence icon signal that, not underlines. */
function ValueButton({
  text,
  onOpen,
  className = "",
  wrap = false,
}: {
  text: string;
  onOpen: () => void;
  className?: string;
  wrap?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      title="View source evidence"
      className={`group/value -mx-1 inline-flex max-w-full items-baseline gap-1.5 rounded px-1 text-left text-foreground transition-colors hover:bg-primary/[0.06] hover:text-primary ${className}`}
    >
      <span className={wrap ? "min-w-0 whitespace-pre-line break-words" : "min-w-0 truncate"}>{text}</span>
      <FileSearch
        aria-hidden="true"
        className="h-3.5 w-3.5 shrink-0 self-center text-primary opacity-0 transition-opacity group-hover/value:opacity-70 group-focus-visible/value:opacity-70"
      />
    </button>
  );
}

// --- A. Detail group ------------------------------------------------------------

function DetailList({ items, onSelect }: { items: FieldItem[]; onSelect: (target: EvidenceTarget) => void }) {
  return (
    <dl className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
      {items.map((item) => {
        const open = () => onSelect(itemTarget(item));
        return (
          <div key={item.id} className="grid gap-x-6 gap-y-0.5 px-4 py-2.5 sm:grid-cols-[minmax(10rem,32%)_1fr]">
            <dt className="text-sm text-text-secondary">{item.label}</dt>
            <dd className="flex min-w-0 flex-wrap items-center justify-between gap-2 text-sm">
              <ValueButton text={formatCellValue(item.cell)} onOpen={open} className="font-medium" wrap />
              <ReviewMark cell={item.cell} onOpen={open} />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

// --- C. Summary block -------------------------------------------------------------

function SummaryBlock({ items, onSelect }: { items: FieldItem[]; onSelect: (target: EvidenceTarget) => void }) {
  return (
    <dl className="max-w-md rounded-xl border border-border bg-surface px-4 py-2">
      {items.map((item) => {
        const open = () => onSelect(itemTarget(item));
        return (
          <div
            key={item.id}
            className={[
              "flex items-baseline justify-between gap-4 py-1.5 text-sm",
              item.emphasis === "total" ? "mt-1 border-t border-border pt-2.5 font-semibold" : "",
            ].join(" ")}
          >
            <dt className={item.emphasis === "total" ? "text-foreground" : "text-text-secondary"}>{item.label}</dt>
            <dd className="flex items-center gap-2">
              <ReviewMark cell={item.cell} onOpen={open} />
              <ValueButton text={formatCellValue(item.cell)} onOpen={open} className="tabular-nums" />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

// --- B. Record grid ------------------------------------------------------------------

type Filter = "all" | "Verified" | "Needs Review";
const PAGE_SIZE = 25;

function RecordGrid({
  section,
  groupLabel,
  documentId,
  onSelect,
  onOpenSource,
}: {
  section: PresentationSection;
  groupLabel: string;
  documentId: string;
  onSelect: (target: EvidenceTarget) => void;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  const dataset = section.dataset!;
  const columns = useMemo(() => section.columns ?? [], [section.columns]);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [openRecord, setOpenRecord] = useState<StagingRecord | null>(null);

  const total = dataset.records.length;
  const flagged = dataset.records.filter((record) => record.record_status === "Needs Review").length;
  const large = total >= 8;
  const searchable = total > 15;
  const records = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return dataset.records.filter((record) => {
      if (filter !== "all" && record.record_status !== filter) return false;
      if (!needle) return true;
      return columns.some((column) => String(record.cells[column.canonical_field]?.value ?? "").toLowerCase().includes(needle));
    });
  }, [dataset.records, filter, query, columns]);
  const pages = Math.max(1, Math.ceil(records.length / PAGE_SIZE));
  const clamped = Math.min(page, pages - 1);
  const paged = records.slice(clamped * PAGE_SIZE, clamped * PAGE_SIZE + PAGE_SIZE);
  const needsDetails = flagged > 0 || (section.detailColumns?.length ?? 0) > 0 || Boolean(dataset.compact);
  const [singular, plural] = section.noun ?? ["record", "records"];
  const identity = columns.find((column) => /description|title|name|clause|far_number|clin/i.test(column.canonical_field)) ?? columns[0];

  function openCell(record: StagingRecord, column: StagingColumn) {
    const cell = record.cells[column.canonical_field];
    if (!cell || isBlank(cell.value)) return;
    const rowName = identity ? String(record.cells[identity.canonical_field]?.value ?? "") : "";
    onSelect({
      context: rowName && identity !== column ? `${section.title ?? groupLabel} · ${rowName}` : section.title ?? groupLabel,
      field: column.display_label,
      cell,
      sourceLabel: cell.source_column?.raw_header ?? null,
      fieldId: column.canonical_field,
      fragments: record.source_columns?.filter(
        (fragment) => fragment.raw_header == null || fragment.raw_header === cell.source_column?.raw_header,
      ),
    });
  }

  return (
    <div className="space-y-2">
      {(total > 1 || large) && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {searchable && (
              <label className="flex min-w-[200px] items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm">
                <Search className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" />
                <input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setPage(0);
                  }}
                  placeholder={`Search ${plural}`}
                  aria-label={`Search ${plural}`}
                  className="w-full bg-transparent outline-none placeholder:text-text-muted"
                />
              </label>
            )}
            {large && flagged > 0 && (
              <div className="flex gap-0.5 rounded-lg border border-border bg-surface-soft p-0.5 text-xs" role="group" aria-label="Review filter">
                {(["all", "Verified", "Needs Review"] as Filter[]).map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={filter === value}
                    onClick={() => {
                      setFilter(value);
                      setPage(0);
                    }}
                    className={[
                      "rounded-md px-2.5 py-1 font-medium",
                      filter === value ? "bg-surface text-foreground shadow-sm" : "text-text-secondary hover:text-foreground",
                    ].join(" ")}
                  >
                    {value === "all" ? "All" : value}
                  </button>
                ))}
              </div>
            )}
          </div>
          <span className="text-xs text-text-muted">
            {records.length === total ? `${total.toLocaleString()} ${total === 1 ? singular : plural}` : `${records.length} of ${total} ${plural}`}
          </span>
        </div>
      )}

      <div className="max-h-[65vh] overflow-auto rounded-xl border border-border bg-surface">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-surface-soft">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.canonical_field}
                  className="whitespace-nowrap px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary"
                >
                  {column.display_label}
                </th>
              ))}
              {needsDetails && (
                <th className="w-px whitespace-nowrap px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
                  Review
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {paged.map((record) => (
              <tr key={record.record_id} className="hover:bg-surface-soft/60">
                {columns.map((column) => {
                  const cell = record.cells[column.canonical_field];
                  const text = cell && !isBlank(cell.value) ? formatCellValue(cell) : "";
                  return (
                    <td key={column.canonical_field} className="max-w-[24rem] px-3 py-2 align-top" title={text}>
                      {text ? (
                        <ValueButton text={text} onOpen={() => openCell(record, column)} />
                      ) : null}
                    </td>
                  );
                })}
                {needsDetails && (
                  <td className="whitespace-nowrap px-3 py-2 text-right align-top">
                    <button
                      type="button"
                      onClick={() => setOpenRecord(record)}
                      className={
                        record.record_status === "Needs Review"
                          ? "rounded-full bg-warning/10 px-2 py-0.5 text-[11px] font-medium text-warning hover:bg-warning/20"
                          : "text-xs text-text-muted hover:text-primary"
                      }
                      aria-label={record.record_status === "Needs Review" ? "Needs Review — details" : "Verified — details"}
                    >
                      {record.record_status === "Needs Review" ? "! Needs Review" : "✓"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!needsDetails && total > 0 && flagged === 0 && dataset.records.every((record) => record.record_status === "Verified") && (
        <p className="text-xs text-text-muted">
          <span className="text-success" aria-hidden="true">✓</span> All {plural} verified against the source
        </p>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-between text-xs text-text-secondary">
          <button type="button" disabled={clamped === 0} onClick={() => setPage(clamped - 1)} className="rounded-md border border-border px-2.5 py-1 disabled:opacity-40">
            Previous
          </button>
          <span>
            Page {clamped + 1} of {pages}
          </span>
          <button type="button" disabled={clamped >= pages - 1} onClick={() => setPage(clamped + 1)} className="rounded-md border border-border px-2.5 py-1 disabled:opacity-40">
            Next
          </button>
        </div>
      )}

      {openRecord && (
        <StagingRecordDrawer
          documentId={documentId}
          dataset={dataset}
          record={openRecord}
          onClose={() => setOpenRecord(null)}
          onOpenSource={onOpenSource}
        />
      )}
    </div>
  );
}

// --- Technical view -------------------------------------------------------------------

/** Every dataset exactly as staged — categories, field ids, source labels,
 * methods, locations — for admin and development review. */
function TechnicalView({
  workbook,
  documentId,
  onOpenSource,
}: {
  workbook: StagingWorkbook;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  const [open, setOpen] = useState(false);
  const [datasetId, setDatasetId] = useState(workbook.datasets[0]?.dataset_id ?? "");
  const dataset = workbook.datasets.find((item) => item.dataset_id === datasetId) ?? workbook.datasets[0];
  if (workbook.datasets.length === 0) return null;
  return (
    <div className="border-t border-dashed border-border pt-3">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="text-xs text-text-muted underline decoration-dotted underline-offset-4 hover:text-text-secondary"
      >
        {open ? "Hide" : "Show"} technical view (all staged datasets)
      </button>
      {open && dataset && (
        <div className="mt-3 space-y-3 rounded-xl border border-dashed border-border bg-surface-soft/60 p-3">
          <div className="flex flex-wrap gap-1">
            {workbook.datasets.map((item) => (
              <button
                key={item.dataset_id}
                type="button"
                aria-pressed={item.dataset_id === dataset.dataset_id}
                onClick={() => setDatasetId(item.dataset_id)}
                className={[
                  "rounded-md px-2 py-0.5 font-mono text-[11px]",
                  item.dataset_id === dataset.dataset_id ? "bg-foreground text-white" : "text-text-secondary hover:bg-surface",
                ].join(" ")}
              >
                {item.dataset_id}
              </button>
            ))}
          </div>
          {dataset.cardinality === "single" ? (
            <StagingFieldList dataset={dataset} onOpenSource={onOpenSource} />
          ) : (
            <StagingDatasetTable dataset={dataset} documentId={documentId} onOpenSource={onOpenSource} />
          )}
        </div>
      )}
    </div>
  );
}
