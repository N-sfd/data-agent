"use client";

import { ChevronDown, X } from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ReviewStatusBadge } from "@/components/staging/review-status";
import SelectCheckbox from "@/components/staging/select-checkbox";
import SelectionToolbar from "@/components/staging/selection-toolbar";
import {
  FROZEN_COLUMNS,
  alternateSummary,
  farColumnLabels,
  farHeading,
  farText,
  farTypeCounts,
  farValue,
  filterFarGroups,
  groupFarRecords,
  visibleFarColumns,
  type FarGroup,
  type ReviewFilter,
} from "@/lib/far-records";
import { getStagingRecord, type StagingDataset, type StagingRecord } from "@/lib/staging-workbook";
import {
  allSelected,
  isSelected,
  rangeBlock,
  setCells,
  someSelected,
  toggleBlock,
  toggleCell,
  useTableSelection,
  type Selection,
} from "@/lib/table-selection";

const PAGE_SIZE = 100;
const REVIEW_COLUMN_WIDTH = 110;
const DETAILS_COLUMN_WIDTH = 64;
const CHECK_COLUMN_WIDTH = 36;
/** 11px uppercase, wide tracking ≈ 7.6px a letter, plus padding and the
 * column's checkbox; long labels still ellipsize past the cap. */
const MAX_HEADER_WIDTH = 240;
function headerWidth(label: string): number {
  return Math.min(MAX_HEADER_WIDTH, Math.round(label.length * 7.6 + 40));
}

const fieldOf = (key: string) => `far.record.${key}`;
/** A grid row's records: the FAR record and the alternates shown in it. */
const idsOf = (group: FarGroup) => [group.record.record_id, ...group.alternates.map((alternate) => alternate.record_id)];

/** FAR Clauses & Provisions as a compact enterprise data grid: one line per
 * FAR record (alternates stay with their record), FAR Number and Title
 * frozen, long values ellipsized — the complete record opens in a drawer. */
export default function FarRecordsView({
  documentId,
  dataset,
  filename,
  partHeading,
}: {
  documentId: string;
  dataset: StagingDataset;
  filename: string;
  partHeading?: string | null;
}) {
  const groups = useMemo(() => groupFarRecords(dataset.records), [dataset.records]);
  const alternateCount = groups.reduce((sum, group) => sum + group.alternates.length, 0);
  const types = useMemo(() => farTypeCounts(groups), [groups]);
  const labels = useMemo(() => farColumnLabels(dataset.columns), [dataset.columns]);
  // A column is at least as wide as its header (checkbox + one-line label).
  const columns = useMemo(
    () => visibleFarColumns(groups, labels).map((column) => ({ ...column, width: Math.max(column.width, headerWidth(column.label)) })),
    [groups, labels],
  );
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");
  const [review, setReview] = useState<ReviewFilter>("all");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<FarGroup | null>(null);

  const filtered = useMemo(() => filterFarGroups(groups, { query, type, review }), [groups, query, type, review]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const rows = filtered.slice(current * PAGE_SIZE, current * PAGE_SIZE + PAGE_SIZE);
  const tableWidth =
    CHECK_COLUMN_WIDTH +
    columns.reduce((sum, column) => sum + column.width, 0) +
    REVIEW_COLUMN_WIDTH +
    DETAILS_COLUMN_WIDTH;
  const frozenLeft = useMemo(
    () =>
      columns
        .slice(0, FROZEN_COLUMNS)
        .map((_, index) => CHECK_COLUMN_WIDTH + columns.slice(0, index).reduce((sum, column) => sum + column.width, 0)),
    [columns],
  );

  // Selection (stable record / field ids): a column header covers every
  // record of the current filters and search, not just this page.
  const [selection, setSelection] = useTableSelection(documentId, dataset.dataset_id, dataset.display_name);
  const [anchor, setAnchor] = useState<{ recordId: string; field: string } | null>(null);
  const fields = useMemo(() => columns.map((column) => fieldOf(column.key)), [columns]);
  const filteredIds = useMemo(() => filtered.flatMap(idsOf), [filtered]);
  const rowOrder = useMemo(() => filtered.map((group) => group.record.record_id), [filtered]);
  const visibleIds = rows.flatMap(idsOf);

  // The latest grid order for Shift+click ranges, read without making the
  // click handler change identity (rows are memoized).
  const rangeContext = useRef({ anchor, rowOrder, fields });
  useEffect(() => {
    rangeContext.current = { anchor, rowOrder, fields };
  });
  const selectCell = useCallback(
    (event: React.MouseEvent, recordId: string, field: string) => {
      const context = rangeContext.current;
      if (event.shiftKey && context.anchor) {
        const block = rangeBlock(context.rowOrder, context.fields, context.anchor, { recordId, field });
        if (block) {
          setSelection((current) => setCells(current, block.recordIds, block.fields, true));
          return;
        }
      }
      setAnchor({ recordId, field });
      // A click (or Ctrl/Cmd+click) toggles the cell, like its checkbox.
      setSelection((current) => toggleCell(current, recordId, field));
    },
    [setSelection],
  );

  function resetPage<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setPage(0);
    };
  }

  return (
    <div>
      <header className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">{farHeading(partHeading)}</h2>
        <p className="mt-0.5 text-sm text-text-secondary">
          {groups.length.toLocaleString()} FAR records
          {alternateCount > 0 ? ` · ${alternateCount.toLocaleString()} alternates within them` : ""} · extracted from{" "}
          {filename || "the source document"}
        </p>
      </header>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={query}
          onChange={(event) => resetPage(setQuery)(event.target.value)}
          placeholder="Search FAR number, title, text…"
          aria-label="Search FAR records"
          className="h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary/50 sm:w-72"
        />
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by record type">
          {[{ type: "all", count: groups.length }, ...types].map((item) => (
            <button
              key={item.type}
              type="button"
              aria-pressed={type === item.type}
              onClick={() => resetPage(setType)(item.type)}
              className={[
                "h-8 rounded-full px-3 text-xs",
                type === item.type
                  ? "bg-primary text-white"
                  : "border border-border text-text-secondary hover:bg-surface-soft",
              ].join(" ")}
            >
              {item.type === "all" ? "All" : item.type}{" "}
              <span className="tabular-nums opacity-70">{item.count.toLocaleString()}</span>
            </button>
          ))}
        </div>
        <label className="relative flex h-8 items-center gap-1 rounded-full border border-border pl-3 pr-1 text-xs text-text-secondary">
          Review:
          <select
            value={review}
            onChange={(event) => resetPage(setReview)(event.target.value as ReviewFilter)}
            aria-label="Review status"
            className="h-full appearance-none bg-transparent pl-1 pr-5 font-medium text-foreground outline-none"
          >
            <option value="all">All</option>
            <option value="Verified">Verified</option>
            <option value="Needs Review">Needs Review</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5" aria-hidden="true" />
        </label>
        <span className="ml-auto text-xs text-text-secondary tabular-nums">
          {filtered.length.toLocaleString()} of {groups.length.toLocaleString()} records
        </span>
      </div>

      <div className="mb-2">
        <SelectionToolbar
          documentId={documentId}
          datasetId={dataset.dataset_id}
          filename={filename}
          selection={selection}
          onClear={() => setSelection(new Map())}
          onSelectVisible={() => setSelection((current) => setCells(current, visibleIds, fields, true))}
          resultCount={filtered.length}
          allResultsSelected={allSelected(selection, filteredIds, fields)}
          onSelectAllResults={() => setSelection((current) => setCells(current, filteredIds, fields, true))}
        />
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-soft px-4 py-10 text-center text-sm text-text-secondary">
          No FAR records match these filters.
        </div>
      ) : (
        <div className="max-h-[70vh] overflow-auto rounded-xl border border-border bg-surface" data-testid="far-grid">
          <table className="table-fixed border-separate border-spacing-0 text-[13px]" style={{ width: tableWidth }}>
            <colgroup>
              <col style={{ width: CHECK_COLUMN_WIDTH }} />
              {columns.map((column) => (
                <col key={column.key} style={{ width: column.width }} />
              ))}
              <col style={{ width: REVIEW_COLUMN_WIDTH }} />
              <col style={{ width: DETAILS_COLUMN_WIDTH }} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 top-0 z-30 h-8 border-b border-border bg-surface-soft text-center">
                  {/* The page only; "Select all N results" is offered in the toolbar. */}
                  <SelectCheckbox
                    checked={allSelected(selection, visibleIds, fields)}
                    indeterminate={someSelected(selection, visibleIds, fields)}
                    onChange={() => setSelection((current) => toggleBlock(current, visibleIds, fields))}
                    label={`Select all ${rows.length} records on this page`}
                  />
                </th>
                {columns.map((column, index) => (
                  <th
                    key={column.key}
                    scope="col"
                    className={[
                      "sticky top-0 h-8 truncate border-b border-border bg-surface-soft px-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary",
                      index < FROZEN_COLUMNS ? "z-30" : "z-20",
                      index === FROZEN_COLUMNS - 1 ? "border-r" : "",
                    ].join(" ")}
                    style={index < FROZEN_COLUMNS ? { left: frozenLeft[index] } : undefined}
                    title={column.label}
                  >
                    <span className="flex items-center gap-1.5">
                      <SelectCheckbox
                        checked={allSelected(selection, filteredIds, [fieldOf(column.key)])}
                        indeterminate={someSelected(selection, filteredIds, [fieldOf(column.key)])}
                        onChange={() => setSelection((current) => toggleBlock(current, filteredIds, [fieldOf(column.key)]))}
                        label={`Select column ${column.label}`}
                        className="col-check"
                      />
                      <span className="truncate">{column.label}</span>
                    </span>
                  </th>
                ))}
                <th scope="col" className="sticky top-0 z-20 h-8 border-b border-border bg-surface-soft px-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
                  Review
                </th>
                <th scope="col" className="sticky top-0 z-20 h-8 border-b border-border bg-surface-soft px-2">
                  <span className="sr-only">Details</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((group) => (
                <FarRow
                  key={group.record.record_id}
                  group={group}
                  columns={columns}
                  frozenLeft={frozenLeft}
                  fields={fields}
                  selection={selection}
                  onCellClick={selectCell}
                  onSelect={setSelection}
                  onOpen={setOpen}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <nav className="mt-3 flex items-center justify-between text-xs text-text-secondary" aria-label="Pagination">
          <button
            type="button"
            disabled={current === 0}
            onClick={() => setPage(current - 1)}
            className="rounded-md border border-border px-2.5 py-1 font-medium disabled:opacity-40"
          >
            Previous
          </button>
          <span className="tabular-nums">
            {(current * PAGE_SIZE + 1).toLocaleString()}–{Math.min(filtered.length, (current + 1) * PAGE_SIZE).toLocaleString()} of{" "}
            {filtered.length.toLocaleString()} · Page {current + 1} of {pages}
          </span>
          <button
            type="button"
            disabled={current >= pages - 1}
            onClick={() => setPage(current + 1)}
            className="rounded-md border border-border px-2.5 py-1 font-medium disabled:opacity-40"
          >
            Next
          </button>
        </nav>
      )}

      {open && (
        <FarRecordDrawer
          documentId={documentId}
          datasetId={dataset.dataset_id}
          labels={labels}
          group={open}
          filename={filename}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}


type SelectionSetter = (next: Selection | ((current: Selection) => Selection)) => void;

interface FarRowProps {
  group: FarGroup;
  columns: ReturnType<typeof visibleFarColumns>;
  frozenLeft: number[];
  fields: string[];
  selection: Selection;
  onCellClick: (event: React.MouseEvent, recordId: string, field: string) => void;
  onSelect: SelectionSetter;
  onOpen: (group: FarGroup) => void;
}

/** One grid row. Re-renders only when its own records' selection (or the
 * grid's layout) changes — a click elsewhere leaves it untouched. */
const FarRow = memo(function FarRow({ group, columns, frozenLeft, fields, selection, onCellClick, onSelect, onOpen }: FarRowProps) {
  return (
    <tr
      key={group.record.record_id}
      tabIndex={0}
      // A click selects a cell; Details or Enter opens the record.
      onKeyDown={(event) => {
        if (event.key === "Enter" && event.target === event.currentTarget) onOpen(group);
      }}
      aria-label={`${farValue(group.record, "far_number")} ${farValue(group.record, "title")}`}
      className="group cursor-cell focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary"
    >
      <td className="sticky left-0 z-10 h-8 border-b border-border/70 bg-surface text-center align-middle">
        <SelectCheckbox
          checked={allSelected(selection, idsOf(group), fields)}
          indeterminate={someSelected(selection, idsOf(group), fields)}
          onChange={() => onSelect((current) => toggleBlock(current, idsOf(group), fields))}
          label={`Select record ${farValue(group.record, "far_number")}`}
        />
      </td>
      {columns.map((column, index) => {
        const text = column.key === "alternate" ? alternateSummary(group) : farValue(group.record, column.key);
        const field = fieldOf(column.key);
        const picked = isSelected(selection, group.record.record_id, field);
        return (
          <td
            key={column.key}
            onMouseDown={(event) => event.shiftKey && event.preventDefault()}
            onClick={(event) => onCellClick(event, group.record.record_id, field)}
            aria-selected={picked}
            className={[
              picked ? "cell-selected" : "",
              "h-8 border-b border-border/70 px-2 align-middle group-hover:bg-surface-soft",
              index < FROZEN_COLUMNS ? "sticky z-10 bg-surface" : "",
              index === FROZEN_COLUMNS - 1 ? "border-r" : "",
              index === 0 ? "font-medium tabular-nums" : "",
            ].join(" ")}
            style={index < FROZEN_COLUMNS ? { left: frozenLeft[index] } : undefined}
            title={text.length > 40 ? text.slice(0, 300) : undefined}
          >
            <span className="flex min-w-0 items-center gap-1.5">
              <SelectCheckbox
                small
                className="cell-check"
                checked={picked}
                onChange={() => onSelect((current) => toggleCell(current, group.record.record_id, field))}
                label={`Select ${column.label} of ${farValue(group.record, "far_number")}`}
              />
              <span className={`block min-w-0 flex-1 truncate ${text ? "text-foreground" : "text-text-muted"}`}>
                {text ? text.replace(/\s+/g, " ") : "—"}
              </span>
            </span>
          </td>
        );
      })}
      <td className="h-8 border-b border-border/70 px-2 align-middle group-hover:bg-surface-soft">
        <ReviewStatusBadge status={group.status} />
      </td>
      <td className="h-8 border-b border-border/70 px-2 text-right align-middle group-hover:bg-surface-soft">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onOpen(group);
          }}
          className="text-xs font-medium text-primary hover:underline"
        >
          Details
        </button>
      </td>
    </tr>
  );
}, (previous, next) =>
  previous.group === next.group &&
  previous.columns === next.columns &&
  previous.frozenLeft === next.frozenLeft &&
  previous.fields === next.fields &&
  previous.onCellClick === next.onCellClick &&
  previous.onSelect === next.onSelect &&
  previous.onOpen === next.onOpen &&
  idsOf(next.group).every((id) => previous.selection.get(id) === next.selection.get(id)),
);

function Paragraphs({ text }: { text: string }) {
  return (
    <div className="space-y-2 leading-6">
      {text
        .split(/\n+/)
        .filter((line) => line.trim())
        .map((line, index) => (
          <p key={index} className="whitespace-pre-wrap break-words">
            {line}
          </p>
        ))}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-text-secondary">{label}</h3>
      <div className="mt-1.5 text-sm text-foreground">{children}</div>
    </section>
  );
}

/** The complete FAR record: headline, hierarchy, then each long value in
 * full; alternates under their record; the exact source location. */
function FarRecordDrawer({
  documentId,
  datasetId,
  group,
  filename,
  onClose,
  labels,
}: {
  documentId: string;
  datasetId: string;
  labels: Record<string, string>;
  group: FarGroup;
  filename: string;
  onClose: () => void;
}) {
  const record = group.record;
  const closeRef = useRef<HTMLButtonElement>(null);
  const [full, setFull] = useState<{ id: string; record: StagingRecord | null } | null>(null);

  useEffect(() => {
    closeRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // The full record carries the source location and review reasons.
  useEffect(() => {
    let cancelled = false;
    getStagingRecord(documentId, datasetId, record.record_id)
      .then((loaded) => {
        if (!cancelled) setFull({ id: record.record_id, record: loaded });
      })
      .catch(() => {
        if (!cancelled) setFull({ id: record.record_id, record: null });
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, datasetId, record.record_id]);

  const loaded = full && full.id === record.record_id ? full.record : null;
  const locator = loaded
    ? Object.values(loaded.cells).find((cell) => cell.provenance?.source_locator)?.provenance?.source_locator
    : null;
  const reasons = loaded
    ? Object.values(loaded.cells)
        .filter((cell) => cell.review_status === "Needs Review")
        .flatMap((cell) => cell.review_reasons.map((reason) => `${cell.display_label}: ${reason}`))
    : [];

  const number = farValue(record, "far_number");
  const title = farValue(record, "title");
  const kind = farValue(record, "record_type");
  const meta = [
    kind,
    [farValue(record, "far_part"), farValue(record, "far_part_title")].filter(Boolean).join(" — "),
    farValue(record, "far_subpart"),
    farValue(record, "far_section") && `Section ${farValue(record, "far_section")}`,
    farValue(record, "revision_date"),
    farValue(record, "record_status") === "Reserved" ? "Reserved" : "",
  ].filter(Boolean);
  const body = farText(record, labels);
  // Part 53: what the record says about a form.
  const formFields = ["form_number", "form_name", "form_type", "prescribing_reference", "form_usage", "supersession"]
    .map((key) => ({ key, label: labels[key] ?? key, value: farValue(record, key) }))
    .filter((field) => field.value);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={`${number} details`}>
      <button type="button" aria-label="Close details" tabIndex={-1} className="flex-1 bg-black/25" onClick={onClose} />
      <aside className="flex h-full w-full max-w-2xl flex-col border-l border-border bg-surface shadow-xl">
        <header className="flex items-start justify-between gap-3 border-b border-border px-6 py-5">
          <div className="min-w-0">
            <h2 className="text-base font-semibold leading-6 text-foreground">
              {number}
              {title ? ` — ${title}` : ""}
            </h2>
            <p className="mt-1 text-sm text-text-secondary">{meta.join(" · ")}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <ReviewStatusBadge status={group.status} />
            <button
              ref={closeRef}
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded-md p-1 text-text-secondary hover:bg-surface-soft"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {reasons.length > 0 && (
            <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 text-sm">
              <p className="font-medium text-warning">Needs review</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-text-secondary">
                {reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}
          {farValue(record, "description") && <Section label="Description"><Paragraphs text={farValue(record, "description")} /></Section>}
          {farValue(record, "prescription") && (
            <Section label="Prescription / Usage"><Paragraphs text={farValue(record, "prescription")} /></Section>
          )}
          {farValue(record, "prescription_reference") && (
            <Section label="Prescription Reference">{farValue(record, "prescription_reference")}</Section>
          )}
          {group.alternates.length === 0 ? (
            farValue(record, "alternate") && <Section label="Alternate">{farValue(record, "alternate")}</Section>
          ) : (
            <Section label="Alternate">
              <div className="space-y-3">
                {group.alternates.map((alternate) => {
                  const altText = farText(alternate)?.text;
                  return (
                    <div key={alternate.record_id} className="rounded-lg border border-border p-3">
                      <p className="font-medium">
                        {farValue(alternate, "description") || farValue(alternate, "alternate")}
                        {farValue(alternate, "record_status") === "Reserved" ? " · Reserved" : ""}
                      </p>
                      {farValue(alternate, "prescription") && (
                        <p className="mt-1 text-text-secondary">{farValue(alternate, "prescription")}</p>
                      )}
                      {farValue(alternate, "prescription_reference") && (
                        <p className="mt-1 text-xs text-text-muted">
                          Prescription reference {farValue(alternate, "prescription_reference")}
                        </p>
                      )}
                      {altText && (
                        <div className="mt-2">
                          <Paragraphs text={altText} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Section>
          )}
          {formFields.length > 0 && (
            <Section label="Form">
              <dl className="grid grid-cols-[minmax(8rem,35%)_1fr] gap-x-3 gap-y-1">
                {formFields.map((field) => (
                  <div key={field.key} className="contents">
                    <dt className="text-text-secondary">{field.label}</dt>
                    <dd className="break-words">{field.value}</dd>
                  </div>
                ))}
              </dl>
            </Section>
          )}
          {farValue(record, "cross_references") && (
            <Section label="Cross References">{farValue(record, "cross_references")}</Section>
          )}
          {body && <Section label={body.label}><Paragraphs text={body.text} /></Section>}
          <Section label="Source Reference">
            <p className="break-words">{farValue(record, "source_reference") || filename}</p>
            {locator && (
              <p className="mt-1 break-all font-mono text-[11px] text-text-muted">
                {filename} → {locator.element_id ? `#${locator.element_id}` : ""}
                {locator.dom_path ? ` (${locator.dom_path})` : ""}
              </p>
            )}
          </Section>
        </div>
      </aside>
    </div>
  );
}
