"use client";

import { FileSearch, MoreHorizontal, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import EvidenceDrawer, { type EvidenceTarget } from "@/components/staging/evidence-drawer";
import { cellSourceRequest, formatCellValue } from "@/components/staging/review-status";
import ResizeHandle, { useGridSizes } from "@/components/staging/resize-handle";
import SelectCheckbox from "@/components/staging/select-checkbox";
import SelectionToolbar from "@/components/staging/selection-toolbar";
import StagingDatasetTable from "@/components/staging/staging-dataset-table";
import StagingFieldList from "@/components/staging/staging-field-list";
import StagingRecordDrawer from "@/components/staging/staging-record-drawer";
import {
  composePresentation,
  isBlank,
  type FieldItem,
  type FieldSource,
  type PresentationGroup,
  type PresentationSection,
} from "@/lib/presentation-manifest";
import {
  downloadSelectedFieldsExport,
  type SelectedExportFormat,
  type SelectedFieldRef,
  type StagingCell,
  type StagingColumn,
  type StagingRecord,
  type StagingWorkbook,
} from "@/lib/staging-workbook";
import {
  allSelected,
  isSelected,
  rangeBlock,
  setCells,
  someSelected,
  toggleBlock,
  toggleCell,
  useTableSelection,
} from "@/lib/table-selection";

export interface MoreAction {
  label: string;
  onSelect: () => void;
}

interface WorkspaceProps {
  workbook: StagingWorkbook;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
  /** Fallback when there is no source panel: show the value in the Source view. */
  onViewInDocument?: (target: EvidenceTarget) => void;
  /** Reviewer/developer views offered under "More" (extraction details,
   * source structure, diagnostics); raw staging data is always offered. */
  moreActions?: MoreAction[];
  /** Off where the page already names the document (its own heading). */
  showHeading?: boolean;
  /** Off where the page has its own technical tabs (Staging …). */
  showTechnical?: boolean;
}

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Business display only: "2026-09-23" reads "Sep 23, 2026". The stored
 * and exported value stays ISO. */
export function displayText(text: string): string {
  const match = ISO_DATE.exec(text.trim());
  if (!match) return text;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  if (Number.isNaN(date.getTime()) || date.getUTCDate() !== Number(match[3])) return text;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

/** The business-facing workspace: what information is in this document.
 * How it was extracted lives behind Details (the evidence drawer) and the
 * collapsed technical view. */
export default function PresentationWorkspace({
  workbook,
  documentId,
  onOpenSource,
  onViewInDocument,
  moreActions = [],
  showHeading = true,
  showTechnical: offerTechnical = true,
}: WorkspaceProps) {
  const manifest = useMemo(() => composePresentation(workbook), [workbook]);
  const [active, setActive] = useState(manifest.groups[0]?.id ?? "");
  const [target, setTarget] = useState<EvidenceTarget | null>(null);
  const [showTechnical, setShowTechnical] = useState(false);
  const technicalRef = useRef<HTMLDivElement>(null);
  const current = manifest.groups.find((group) => group.id === active) ?? manifest.groups[0];

  // Values picked in label / value lists (Supplier, Charges & Totals …),
  // across tabs, by item id; exported together as Section | Field | Value.
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const pick = (items: FieldItem[], on: boolean) =>
    setPicked((previous) => {
      const next = new Set(previous);
      for (const item of items) {
        if (!item.source) continue;
        if (on) next.add(item.id);
        else next.delete(item.id);
      }
      return next;
    });
  // Display order, each stored value once.
  const pickedItems = useMemo(() => {
    const seen = new Set<string>();
    return manifest.groups
      .flatMap((group) => group.sections)
      .filter((section) => section.pattern !== "grid")
      .flatMap((section) => section.items)
      .filter((item) => {
        if (!picked.has(item.id) || !item.source || seen.has(item.id)) return false;
        seen.add(item.id);
        return true;
      });
  }, [manifest, picked]);
  const listItems = (current?.sections ?? []).filter((section) => section.pattern !== "grid").flatMap((section) => section.items);

  const viewInDocument = (evidence: EvidenceTarget) => {
    setTarget(null);
    const request = cellSourceRequest(evidence.cell, `${evidence.fieldId ?? evidence.cell.canonical_field}:${Date.now()}`);
    if (onOpenSource && request) onOpenSource({ ...request, label: evidence.field });
    else onViewInDocument?.(evidence);
  };

  const hasHeader = showHeading || Boolean(manifest.subtitle) || moreActions.length > 0 || offerTechnical;

  return (
    // While anything is picked, every list checkbox shows (selection mode).
    <div className={`space-y-5 ${picked.size > 0 ? "list-selecting" : ""}`}>
      {hasHeader && (
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {showHeading && <h3 className="text-lg font-semibold tracking-tight text-foreground">{manifest.heading}</h3>}
          {manifest.subtitle && (
            <p className={showHeading ? "mt-0.5 text-sm text-text-secondary" : "text-sm font-medium text-foreground"}>
              {manifest.subtitle}
            </p>
          )}
        </div>
        {(offerTechnical || moreActions.length > 0) && (
          <MoreMenu
            actions={[
              ...moreActions,
              ...(offerTechnical
                ? [
                    {
                      label: "Raw staging data",
                      onSelect: () => {
                        setShowTechnical(true);
                        requestAnimationFrame(() => technicalRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
                      },
                    },
                  ]
                : []),
            ]}
          />
        )}
      </div>
      )}

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

      {pickedItems.length > 0 && (
        <SelectionToolbar
          documentId={documentId}
          datasetId=""
          filename={workbook.document_filename}
          selection={new Map(pickedItems.map((item) => [item.id, new Set(["value"])]))}
          summary={`${pickedItems.length} value${pickedItems.length === 1 ? "" : "s"} selected`}
          onClear={() => setPicked(new Set())}
          onSelectVisible={() => pick(listItems, true)}
          exportSelection={(format) =>
            downloadSelectedFieldsExport(
              documentId,
              format,
              pickedItems.flatMap((item) => (item.source ? [fieldRef(item.source)] : [])),
              workbook.document_filename,
            )
          }
        />
      )}

      {current ? (
        <GroupBody
          group={current}
          documentId={documentId}
          onSelect={setTarget}
          onOpenSource={onOpenSource}
          picked={picked}
          onPick={pick}
        />
      ) : (
        <p className="rounded-xl border border-border bg-surface-soft px-4 py-8 text-center text-sm text-text-secondary">
          No business information was found in this document. Use Source to inspect the file.
        </p>
      )}

      {showTechnical && (
        <div ref={technicalRef}>
          <TechnicalView workbook={workbook} documentId={documentId} onOpenSource={onOpenSource} onClose={() => setShowTechnical(false)} />
        </div>
      )}

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

/** Selection in a label / value list: which values are picked, and a
 * setter for a set of them (a row, or a whole section). */
interface ListPicking {
  picked: ReadonlySet<string>;
  onPick: (items: FieldItem[], on: boolean) => void;
}

function fieldRef(source: FieldSource): SelectedFieldRef {
  return { dataset_id: source.datasetId, record_id: source.recordId, field: source.field };
}

/** A list section's checkbox: every selectable value in it. */
function SectionCheckbox({ items, label, picked, onPick }: { items: FieldItem[]; label: string } & ListPicking) {
  const selectable = items.filter((item) => item.source);
  if (selectable.length === 0) return null;
  const count = selectable.filter((item) => picked.has(item.id)).length;
  const all = count === selectable.length;
  return (
    <SelectCheckbox
      className="list-check"
      checked={all}
      indeterminate={count > 0}
      onChange={() => onPick(selectable, !all)}
      label={`Select all values in ${label}`}
    />
  );
}

/** A list row's checkbox (a spacer for a value with no stored cell). */
function ItemCheckbox({ item, picked, onPick }: { item: FieldItem } & ListPicking) {
  if (!item.source) return <span className="inline-block w-3.5 shrink-0" aria-hidden="true" />;
  const on = picked.has(item.id);
  return (
    <SelectCheckbox className="list-check" checked={on} onChange={() => onPick([item], !on)} label={`Select ${item.label}`} />
  );
}

function GroupBody({
  group,
  documentId,
  onSelect,
  onOpenSource,
  picked,
  onPick,
}: {
  group: PresentationGroup;
  documentId: string;
  onSelect: (target: EvidenceTarget) => void;
  onOpenSource?: (request: SourceViewRequest) => void;
} & ListPicking) {
  // A tab may offer alternative views of the same records (Contract View /
  // Transformation View); sections without a view always show.
  const views = [...new Set(group.sections.map((section) => section.view).filter((view): view is string => Boolean(view)))];
  const [view, setView] = useState(views[0] ?? "");
  const activeView = views.includes(view) ? view : views[0];
  const sections = group.sections.filter((section) => !section.view || section.view === activeView);
  return (
    <div className="space-y-6">
      {views.length > 1 && (
        <div className="flex gap-0.5 self-start rounded-lg border border-border bg-surface-soft p-0.5 text-xs" role="group" aria-label={`${group.label} view`}>
          {views.map((name) => (
            <button
              key={name}
              type="button"
              aria-pressed={name === activeView}
              onClick={() => setView(name)}
              className={[
                "rounded-md px-3 py-1 font-medium",
                name === activeView ? "bg-surface text-foreground shadow-sm" : "text-text-secondary hover:text-foreground",
              ].join(" ")}
            >
              {name}
            </button>
          ))}
        </div>
      )}
      {sections.map((section) => (
        <section key={section.id} aria-label={section.title ?? group.label} className="space-y-2">
          {section.supertitle && (
            <h3 className="border-b border-border pb-1 pt-2 text-sm font-semibold text-foreground">{section.supertitle}</h3>
          )}
          {section.title && (
            // The checkbox sits beside the heading, not in it (the heading's name stays the title).
            <div className="list-row flex items-center gap-2">
              {section.pattern !== "grid" && (
                <SectionCheckbox items={section.items} label={section.title} picked={picked} onPick={onPick} />
              )}
              {section.pattern === "card" ? (
                <h4 className="text-sm font-semibold text-foreground">{section.title}</h4>
              ) : (
                <h4 className="text-xs font-semibold uppercase tracking-[0.08em] text-text-secondary">{section.title}</h4>
              )}
            </div>
          )}
          {section.note && <p className="text-xs text-text-muted">{section.note}</p>}
          {section.pattern === "grid" ? (
            <RecordGrid section={section} groupLabel={group.label} documentId={documentId} onSelect={onSelect} onOpenSource={onOpenSource} />
          ) : section.pattern === "summary" ? (
            <SummaryBlock items={section.items} onSelect={onSelect} picked={picked} onPick={onPick} />
          ) : section.pattern === "card" ? (
            <SummaryCard items={section.items} onSelect={onSelect} picked={picked} onPick={onPick} />
          ) : section.pattern === "text" ? (
            <TextBlock items={section.items} onSelect={onSelect} picked={picked} />
          ) : (
            <DetailList items={section.items} onSelect={onSelect} picked={picked} onPick={onPick} />
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
  whole = false,
}: {
  text: string;
  onOpen: () => void;
  className?: string;
  wrap?: boolean;
  /** Never ellipsized (amounts): one line, at its full width. */
  whole?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      title="View source evidence"
      className={`group/value -mx-1 inline-flex max-w-full items-baseline gap-1.5 rounded px-1 text-left text-foreground transition-colors hover:bg-primary/[0.06] hover:text-primary ${className}`}
    >
      <span className={wrap ? "min-w-0 whitespace-pre-line break-words" : whole ? "whitespace-nowrap" : "min-w-0 truncate"}>{text}</span>
      <FileSearch
        aria-hidden="true"
        className="h-3.5 w-3.5 shrink-0 self-center text-primary opacity-0 transition-opacity group-hover/value:opacity-70 group-focus-visible/value:opacity-70"
      />
    </button>
  );
}

// --- A0. Summary card --------------------------------------------------------------

/** A document-summary card: label over value, two or three per row. Each
 * value still opens its source evidence. */
function SummaryCard({ items, onSelect, picked, onPick }: { items: FieldItem[]; onSelect: (target: EvidenceTarget) => void } & ListPicking) {
  return (
    <dl className="grid gap-x-8 gap-y-4 rounded-xl border border-border bg-surface px-5 py-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => {
        const open = () => onSelect(itemTarget(item));
        const text = formatCellValue(item.cell);
        return (
          <div key={item.id} className={`list-row min-w-0 ${text.length > 80 ? "sm:col-span-2 lg:col-span-3" : ""}`}>
            <dt className="flex items-center gap-1.5 text-xs text-text-secondary">
              <ItemCheckbox item={item} picked={picked} onPick={onPick} />
              {item.label}
            </dt>
            <dd className="mt-0.5 flex min-w-0 flex-wrap items-center gap-2 pl-5 text-sm">
              <ValueButton text={displayText(text)} onOpen={open} className="font-medium" wrap />
              <ReviewMark cell={item.cell} onOpen={open} />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

// --- A1. Document text ----------------------------------------------------------

/** A section of the document's own text: each printed line as a line
 * (bullets and wrapped lines already resolved), with its evidence. */
function TextBlock({
  items,
  onSelect,
  picked,
}: {
  items: FieldItem[];
  onSelect: (target: EvidenceTarget) => void;
  picked: ReadonlySet<string>;
}) {
  return (
    <div className="space-y-2">
      {items.map((item) => {
        const open = () => onSelect(itemTarget(item));
        const lines = formatCellValue(item.cell).split("\n").filter((line) => line.trim());
        return (
          <div
            key={item.id}
            className={`rounded-xl border border-border bg-surface px-5 py-4 ${picked.has(item.id) ? "cell-selected" : ""}`}
          >
            <div className="space-y-1.5 text-sm leading-relaxed text-foreground">
              {lines.map((line, index) => (
                <p key={index} className="break-words">
                  {line}
                </p>
              ))}
            </div>
            <div className="mt-3 flex items-center gap-3">
              <ReviewMark cell={item.cell} onOpen={open} />
              <button
                type="button"
                onClick={open}
                className="inline-flex items-center gap-1 text-xs text-text-secondary hover:text-primary"
              >
                <FileSearch className="h-3.5 w-3.5" aria-hidden="true" />
                View source
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// --- A. Detail group ------------------------------------------------------------

function DetailList({ items, onSelect, picked, onPick }: { items: FieldItem[]; onSelect: (target: EvidenceTarget) => void } & ListPicking) {
  return (
    <dl className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
      {items.map((item) => {
        const open = () => onSelect(itemTarget(item));
        return (
          <div
            key={item.id}
            className={`list-row grid gap-x-6 gap-y-0.5 px-4 py-2.5 sm:grid-cols-[minmax(10rem,32%)_1fr] ${picked.has(item.id) ? "cell-selected" : ""}`}
          >
            <dt className="flex items-start gap-2 text-sm text-text-secondary">
              <span className="flex h-5 items-center">
                <ItemCheckbox item={item} picked={picked} onPick={onPick} />
              </span>
              {item.label}
            </dt>
            <dd className="flex min-w-0 flex-wrap items-center justify-between gap-2 text-sm">
              <ValueButton text={displayText(formatCellValue(item.cell))} onOpen={open} className="font-medium" wrap />
              <ReviewMark cell={item.cell} onOpen={open} />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

// --- C. Summary block -------------------------------------------------------------

function SummaryBlock({ items, onSelect, picked, onPick }: { items: FieldItem[]; onSelect: (target: EvidenceTarget) => void } & ListPicking) {
  return (
    <dl className="max-w-md rounded-xl border border-border bg-surface px-4 py-2">
      {items.map((item) => {
        const open = () => onSelect(itemTarget(item));
        return (
          <div
            key={item.id}
            className={[
              "list-row flex items-baseline justify-between gap-4 py-1.5 text-sm",
              item.emphasis === "total" ? "mt-1 border-t border-border pt-2.5 font-semibold" : "",
              picked.has(item.id) ? "cell-selected -mx-2 rounded px-2" : "",
            ].join(" ")}
          >
            <dt className={`flex items-center gap-2 ${item.emphasis === "total" ? "text-foreground" : "text-text-secondary"}`}>
              <ItemCheckbox item={item} picked={picked} onPick={onPick} />
              {item.label}
            </dt>
            <dd className="flex shrink-0 items-center gap-2">
              <ReviewMark cell={item.cell} onOpen={open} />
              <ValueButton text={formatCellValue(item.cell)} onOpen={open} className="tabular-nums" whole />
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
/** A grid cell's padding (px-3 / py-2): a set size is the cell's outer size. */
const CELL_PAD_X = 24;
const CELL_PAD_Y = 16;

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
  const needsDetails =
    !section.inlineReview && (flagged > 0 || (section.detailColumns?.length ?? 0) > 0 || Boolean(dataset.compact));
  const [singular, plural] = section.noun ?? ["record", "records"];
  // Identifiers and other short values are never clipped: in wide target
  // templates, and in contract grids (inline review) where an ID column
  // would otherwise be squeezed ("G.3.1.9…").
  const keepWhole = (text: string) =>
    (columns.length > 8 && text.length <= 32) || (Boolean(section.inlineReview) && text.length <= 16);
  const identity = columns.find((column) => /description|title|name|clause|far_number|clin/i.test(column.canonical_field)) ?? columns[0];

  // Excel-style selection (cell / row / column) with Export Selected, as in
  // the staging data grid. A value still opens its evidence on click.
  // A composed table (no staged dataset of its own) keeps its selection
  // local, so the page's Export menu never offers it as a dataset.
  const [selection, setSelection] = useTableSelection(
    section.cellSources ? undefined : documentId,
    dataset.dataset_id,
    dataset.display_name,
  );
  const [anchor, setAnchor] = useState<{ recordId: string; field: string } | null>(null);
  const fieldIds = useMemo(() => columns.map((column) => column.canonical_field), [columns]);
  const resultIds = useMemo(() => records.map((record) => record.record_id), [records]);
  const pagedIds = paged.map((record) => record.record_id);
  const rowName = (record: StagingRecord) =>
    (identity ? String(record.cells[identity.canonical_field]?.value ?? "") : "") || record.record_id;

  // Excel-style column widths / row heights set by dragging an edge.
  const sizes = useGridSizes();
  const columnStyle = (field: string): React.CSSProperties | undefined => {
    const width = sizes.columns[field];
    return width ? { width: width - CELL_PAD_X, minWidth: width - CELL_PAD_X, maxWidth: width - CELL_PAD_X } : undefined;
  };

  // A table composed for display (not a staged dataset) exports its
  // selected cells by where each value is stored.
  function exportComposed(format: SelectedExportFormat) {
    const refs = resultIds.flatMap((recordId) =>
      fieldIds
        .filter((field) => isSelected(selection, recordId, field))
        .map((field) => section.cellSources?.[recordId]?.[field])
        .filter((source): source is FieldSource => Boolean(source))
        .map(fieldRef),
    );
    if (refs.length === 0) return Promise.reject(new Error("Select a value (not the Item column) to export."));
    return downloadSelectedFieldsExport(documentId, format, refs, dataset.display_name);
  }

  function selectCell(event: React.MouseEvent, recordId: string, field: string) {
    // Clicking the value itself opens its evidence.
    if ((event.target as HTMLElement).closest("button, input")) return;
    if (event.shiftKey && anchor) {
      const block = rangeBlock(resultIds, fieldIds, anchor, { recordId, field });
      if (block) {
        setSelection((current) => setCells(current, block.recordIds, block.fields, true));
        return;
      }
    }
    setAnchor({ recordId, field });
    setSelection((current) => toggleCell(current, recordId, field));
  }

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

      <SelectionToolbar
        documentId={documentId}
        datasetId={dataset.dataset_id}
        filename={dataset.display_name}
        exportSelection={section.cellSources ? exportComposed : undefined}
        selection={selection}
        onClear={() => setSelection(new Map())}
        onSelectVisible={() => setSelection((current) => setCells(current, pagedIds, fieldIds, true))}
        resultCount={resultIds.length}
        allResultsSelected={allSelected(selection, resultIds, fieldIds)}
        onSelectAllResults={() => setSelection((current) => setCells(current, resultIds, fieldIds, true))}
      />

      <div className="max-h-[65vh] overflow-auto rounded-xl border border-border bg-surface">
        {/* Wide target templates scroll sideways instead of squeezing every value. */}
        <table className={columns.length > 8 ? "w-max min-w-full text-sm" : "w-full text-sm"}>
          <thead className="sticky top-0 z-10 bg-surface-soft">
            <tr>
              <th scope="col" className="w-9 px-2 py-2 text-center">
                <SelectCheckbox
                  checked={allSelected(selection, pagedIds, fieldIds)}
                  indeterminate={someSelected(selection, pagedIds, fieldIds)}
                  onChange={() => setSelection((current) => toggleBlock(current, pagedIds, fieldIds))}
                  label={`Select all ${pagedIds.length} ${plural} on this page`}
                />
              </th>
              {columns.map((column) => (
                <th
                  key={column.canonical_field}
                  className="relative whitespace-nowrap px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary"
                >
                  <span className="flex items-center gap-1.5" style={columnStyle(column.canonical_field)}>
                    <SelectCheckbox
                      checked={allSelected(selection, resultIds, [column.canonical_field])}
                      indeterminate={someSelected(selection, resultIds, [column.canonical_field])}
                      onChange={() => setSelection((current) => toggleBlock(current, resultIds, [column.canonical_field]))}
                      label={`Select column ${column.display_label}`}
                      className="col-check"
                    />
                    <span className="min-w-0 truncate" title={column.display_label}>
                      {column.display_label}
                    </span>
                  </span>
                  <ResizeHandle
                    axis="column"
                    label={`Resize column ${column.display_label}`}
                    onResize={(size) => sizes.setColumn(column.canonical_field, size)}
                    onReset={() => sizes.setColumn(column.canonical_field, null)}
                  />
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
            {paged.map((record) => {
              const height = sizes.rows[record.record_id];
              return (
              <tr
                key={record.record_id}
                className={`hover:bg-surface-soft/60 ${height ? "grid-row-wrap" : ""}`}
                style={height ? { height } : undefined}
              >
                <td className="relative w-9 px-2 py-2 text-center align-top">
                  <SelectCheckbox
                    checked={allSelected(selection, [record.record_id], fieldIds)}
                    indeterminate={someSelected(selection, [record.record_id], fieldIds)}
                    onChange={() => setSelection((current) => toggleBlock(current, [record.record_id], fieldIds))}
                    label={`Select ${singular} ${rowName(record)}`}
                  />
                  <ResizeHandle
                    axis="row"
                    label={`Resize ${singular} ${rowName(record)}`}
                    onResize={(size) => sizes.setRow(record.record_id, size)}
                    onReset={() => sizes.setRow(record.record_id, null)}
                  />
                </td>
                {columns.map((column, index) => {
                  const cell = record.cells[column.canonical_field];
                  const text = cell && !isBlank(cell.value) ? displayText(formatCellValue(cell)) : "";
                  // Inline review: the record's identity (clause number,
                  // title) opens its details; review state is a small mark.
                  const opensRecord = section.inlineReview && (index === 0 || column.canonical_field.endsWith(".title"));
                  const picked = isSelected(selection, record.record_id, column.canonical_field);
                  // A hand-set width wins over keeping short values whole.
                  const whole = keepWhole(text) && !sizes.columns[column.canonical_field];
                  const sized = columnStyle(column.canonical_field);
                  return (
                    <td
                      key={column.canonical_field}
                      onMouseDown={(event) => event.shiftKey && event.preventDefault()}
                      onClick={(event) => selectCell(event, record.record_id, column.canonical_field)}
                      aria-selected={picked}
                      // Content-sized (wide) tables: short values (numbers, codes) are
                      // never truncated; long text keeps its ellipsis.
                      className={`max-w-[24rem] cursor-cell px-3 py-2 align-top ${picked ? "cell-selected" : ""} ${whole ? "whitespace-nowrap pr-6" : ""}`}
                      title={text}
                    >
                      <span
                        className={`flex min-w-0 items-baseline gap-1.5 ${height ? "overflow-hidden" : ""}`}
                        style={height ? { ...sized, maxHeight: Math.max(0, height - CELL_PAD_Y) } : sized}
                      >
                      <SelectCheckbox
                        small
                        className="cell-check self-center"
                        checked={picked}
                        onChange={() => setSelection((current) => toggleCell(current, record.record_id, column.canonical_field))}
                        label={`Select ${column.display_label} of ${rowName(record)}`}
                      />
                      <span className="min-w-0 flex-1">
                      {text && section.inlineReview && index === 0 && record.record_status === "Needs Review" ? (
                        <span className="flex min-w-0 items-baseline gap-1">
                          <span className="shrink-0 text-[11px] font-semibold text-warning" title="Needs review — open details" aria-label="Needs review">
                            !
                          </span>
                          <ValueButton text={text} onOpen={() => setOpenRecord(record)} />
                        </span>
                      ) : text ? (
                        <ValueButton
                          text={text}
                          onOpen={() => (opensRecord ? setOpenRecord(record) : openCell(record, column))}
                          className={whole ? "max-w-none" : ""}
                        />
                      ) : null}
                      </span>
                      </span>
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
              );
            })}
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
          hideBlank={section.inlineReview}
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
  onClose,
}: {
  workbook: StagingWorkbook;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
  onClose: () => void;
}) {
  const open = true;
  const [datasetId, setDatasetId] = useState(workbook.datasets[0]?.dataset_id ?? "");
  const dataset = workbook.datasets.find((item) => item.dataset_id === datasetId) ?? workbook.datasets[0];
  if (workbook.datasets.length === 0) return null;
  return (
    <div className="border-t border-dashed border-border pt-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-text-muted">Raw staging data</p>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-text-muted underline decoration-dotted underline-offset-4 hover:text-text-secondary"
        >
          Hide
        </button>
      </div>
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

// --- More menu -------------------------------------------------------------------------

/** Reviewer/developer views, kept out of the normal document navigation. */
function MoreMenu({ actions }: { actions: MoreAction[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  if (actions.length === 0) return null;
  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:text-foreground"
      >
        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
        More
      </button>
      {open && (
        <div role="menu" aria-label="More" className="absolute right-0 top-full z-20 mt-1 w-56 rounded-lg border border-border bg-surface p-1 shadow-lg">
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                action.onSelect();
              }}
              className="block w-full rounded-md px-3 py-2 text-left text-xs text-foreground hover:bg-surface-soft"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
