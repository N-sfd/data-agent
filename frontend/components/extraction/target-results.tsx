"use client";

import { ChevronDown, Download } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  buildFieldRows,
  classifyRowKind,
  type FieldRow,
  type FieldRowStatus,
} from "@/components/extraction/field-row";
import FieldsTable from "@/components/extraction/fields-table";
import FieldsDatasetTable from "@/components/extraction/fields-dataset-table";
import ResultSummaryBar from "@/components/extraction/result-summary-bar";
import TableResult from "@/components/extraction/table-result";
import ValidationIssuesPanel from "@/components/extraction/validation-issues-panel";
import type { SourceViewRequest } from "@/components/source-verification-panel";
import {
  downloadDocumentExportXlsx,
  downloadReviewedJson,
  scalarToExportField,
} from "@/lib/reviewed-export";
import { downloadBlob } from "@/lib/export";
import {
  listTargetCorrections,
  markTargetVerified,
  rejectTargetValue,
  saveTargetCorrection,
} from "@/lib/target-corrections";
import type {
  DocumentTarget,
  ExtractTargetsResult,
  TableTargetResult,
  TargetCorrection,
  TargetType,
  UniversalTable,
} from "@/types/document";

interface TargetResultsProps {
  result: ExtractTargetsResult;
  /** Schema targets used to classify scalar results (contacts vs fields). */
  targets?: DocumentTarget[];
  documentId?: string;
  documentName?: string;
  status?: "complete" | "processing" | "failed" | "partial";
  processingDurationMs?: number | null;
  selectedResultId?: string | null;
  onViewSource?: (request: SourceViewRequest) => void;
}

function tableToUniversalTable(
  table: TableTargetResult,
  index: number,
): UniversalTable {
  return {
    table_id: `${table.target}-${index}`,
    title: table.target,
    headers: table.columns,
    rows: table.rows,
    page_number: table.pages[0] ?? 0,
    confidence: 1,
    source_reference: table.pages.length
      ? `pages ${table.pages.join(", ")}`
      : "",
  };
}

function isClauseLike(name: string): boolean {
  const lower = name.toLowerCase();
  return (
    lower.includes("clause") ||
    lower.includes("far") ||
    lower.includes("dfars") ||
    lower.includes("section") ||
    lower.includes("article")
  );
}

function dedupeClauseTables(tables: TableTargetResult[]): TableTargetResult[] {
  const seen = new Map<string, TableTargetResult>();

  for (const table of tables) {
    const fingerprint = [
      table.target.toLowerCase(),
      table.columns.join("|"),
      JSON.stringify(table.rows.slice(0, 3)),
    ].join("::");

    const existing = seen.get(fingerprint);
    if (!existing) {
      seen.set(fingerprint, table);
      continue;
    }

    const pages = Array.from(
      new Set([...existing.pages, ...table.pages]),
    ).sort((a, b) => a - b);
    seen.set(fingerprint, { ...existing, pages });
  }

  return Array.from(seen.values());
}

const METHOD_FILTER_OPTIONS = [
  { value: "all", label: "All methods" },
  { value: "native", label: "Native" },
  { value: "ai", label: "AI Fallback" },
];

const VALIDATION_FILTER_OPTIONS: { value: "all" | FieldRowStatus; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "extracted", label: "Extracted" },
  { value: "not_found", label: "Not found" },
  { value: "empty", label: "Empty" },
  { value: "low_confidence", label: "Needs review" },
  { value: "validation_failed", label: "Unverified" },
];

function matchesMethodFilter(row: FieldRow, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "ai") return row.extraction_method === "ai";
  return row.extraction_method !== "ai";
}

function isInternalFormName(name: string): boolean {
  if (!name.trim()) return true;
  const stripped = name.trim();
  if (stripped.startsWith("#")) return true;
  if (
    /^(TextField|CheckBox|RadioButton|SignatureField|NumericField|DateTimeField|DropDownList)\d*$/i.test(
      stripped,
    ) ||
    /^(Page\d+|PG\d+[A-Z]*)$/i.test(stripped)
  ) {
    return true;
  }

  let signals = 0;
  if (/topmostSubform|\bsubform\b|\bxfa\b|\bform\d+\b/i.test(stripped)) {
    signals += 2;
  }
  if (/\bPage\d+\b|\bPG\d+[A-Z]*\b/i.test(stripped)) {
    signals += 1;
  }
  if (/\[\d+\]/.test(stripped)) {
    signals += 1;
  }
  if (
    /TextField\d*|CheckBox\d*|RadioButton\d*|SignatureField\d*|NumericField\d*|DateTimeField\d*|DropDownList\d*/i.test(
      stripped,
    )
  ) {
    signals += 1;
  }
  return signals >= 2;
}

function isInternalKey(key: string, label: string): boolean {
  return isInternalFormName(key) || isInternalFormName(label);
}

export default function TargetResults({
  result,
  targets = [],
  documentId,
  documentName,
  status = "complete",
  processingDurationMs,
  selectedResultId = null,
  onViewSource,
}: TargetResultsProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [confidenceFilter, setConfidenceFilter] = useState<
    "all" | "high" | "medium" | "low"
  >("all");
  const [methodFilter, setMethodFilter] = useState("all");
  const [validationFilter, setValidationFilter] = useState<"all" | FieldRowStatus>(
    "all",
  );
  const [onlyWithValues, setOnlyWithValues] = useState(false);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [activeTab, setActiveTab] = useState<"fields" | "tables">("fields");
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement | null>(null);
  const [corrections, setCorrections] = useState<Map<string, TargetCorrection>>(
    new Map(),
  );

  useEffect(() => {
    if (!exportMenuOpen) return;
    function handleClickOutside(event: MouseEvent) {
      if (!exportMenuRef.current?.contains(event.target as Node)) {
        setExportMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [exportMenuOpen]);

  useEffect(() => {
    if (!documentId) return;
    let cancelled = false;
    listTargetCorrections(documentId)
      .then((list) => {
        if (cancelled) return;
        setCorrections(new Map(list.map((c) => [c.normalized_key, c])));
      })
      .catch(() => {
        // Corrections are a review-quality-of-life feature — if they
        // fail to load, the raw extracted values still render fine.
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  const typeByLabel = new Map<string, TargetType>();
  const labelByKey = new Map<string, string>();
  for (const target of targets) {
    typeByLabel.set(target.label.toLowerCase(), target.target_type);
    typeByLabel.set(target.key.toLowerCase(), target.target_type);
    labelByKey.set(target.key, target.label);
  }

  const { meaningfulMissing, internalMissingCount } = useMemo(() => {
    const meaningful: { key: string; label: string }[] = [];
    let internalCount = 0;
    for (const key of result.unresolved_targets) {
      const label = labelByKey.get(key) ?? key;
      if (isInternalKey(key, label)) {
        internalCount += 1;
      } else {
        meaningful.push({ key, label });
      }
    }
    return { meaningfulMissing: meaningful, internalMissingCount: internalCount };
    // labelByKey is rebuilt from `targets` every render but is
    // value-equivalent when `targets` hasn't changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result.unresolved_targets, targets]);

  const allRows = useMemo(
    () => buildFieldRows(result.scalars, meaningfulMissing, corrections),
    [result.scalars, meaningfulMissing, corrections],
  );

  const confidenceCounts = useMemo(() => {
    const counts = { high: 0, medium: 0, low: 0 };
    for (const scalar of result.scalars) {
      counts[scalar.confidence_band] += 1;
    }
    return counts;
  }, [result.scalars]);

  const issueCount = useMemo(
    () => allRows.filter((row) => row.status !== "extracted").length,
    [allRows],
  );

  const filteredRows = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return allRows.filter((row) => {
      if (
        confidenceFilter !== "all" &&
        row.confidence_band !== confidenceFilter
      ) {
        return false;
      }
      if (!matchesMethodFilter(row, methodFilter)) return false;
      if (validationFilter !== "all" && row.status !== validationFilter) {
        return false;
      }
      if (onlyWithValues && (row.status === "empty" || row.status === "not_found")) {
        return false;
      }
      if (onlyMissing && row.status !== "not_found") return false;
      if (!query) return true;
      const value = String(row.value ?? "").toLowerCase();
      return row.label.toLowerCase().includes(query) || value.includes(query);
    });
  }, [
    allRows,
    searchQuery,
    confidenceFilter,
    methodFilter,
    validationFilter,
    onlyWithValues,
    onlyMissing,
  ]);

  const contactRows: FieldRow[] = [];
  const identifierRows: FieldRow[] = [];
  const fieldRows: FieldRow[] = [];

  for (const row of filteredRows) {
    const kind = classifyRowKind(row, typeByLabel);
    if (kind === "contact") contactRows.push(row);
    else if (kind === "identifier") identifierRows.push(row);
    else fieldRows.push(row);
  }

  const dataTables = result.tables.filter(
    (table) => !isClauseLike(table.target),
  );
  const clauseTables = dedupeClauseTables(
    result.tables.filter((table) => isClauseLike(table.target)),
  );

  async function handleSaveCorrection(row: FieldRow, correctedValue: string) {
    if (!documentId) return;
    const originalValue = row.correction
      ? row.correction.original_value
      : row.value;
    const saved = await saveTargetCorrection(documentId, row.id, {
      originalValue,
      correctedValue,
      evidence: row.evidence
        ? {
            page_number: row.evidence.page_number,
            source_text: row.evidence.source_text,
            source_reference: row.evidence.source_reference,
          }
        : null,
    });
    setCorrections((prev) => {
      const next = new Map(prev);
      next.set(row.id, saved);
      return next;
    });
  }

  async function handleMarkVerified(row: FieldRow) {
    if (!documentId) return;
    const originalValue = row.correction ? row.correction.original_value : row.value;
    const saved = await markTargetVerified(
      documentId,
      row.id,
      originalValue,
      row.evidence
        ? {
            page_number: row.evidence.page_number,
            source_text: row.evidence.source_text,
            source_reference: row.evidence.source_reference,
          }
        : null,
    );
    setCorrections((prev) => {
      const next = new Map(prev);
      next.set(row.id, saved);
      return next;
    });
  }

  async function handleReject(row: FieldRow) {
    if (!documentId) return;
    const originalValue = row.correction ? row.correction.original_value : row.value;
    const saved = await rejectTargetValue(
      documentId,
      row.id,
      originalValue,
      row.evidence
        ? {
            page_number: row.evidence.page_number,
            source_text: row.evidence.source_text,
            source_reference: row.evidence.source_reference,
          }
        : null,
    );
    setCorrections((prev) => {
      const next = new Map(prev);
      next.set(row.id, saved);
      return next;
    });
  }

  function handleIssueClick(rowId: string) {
    setSearchQuery("");
    setConfidenceFilter("all");
    setMethodFilter("all");
    setValidationFilter("all");
    setOnlyWithValues(false);
    setOnlyMissing(false);

    requestAnimationFrame(() => {
      const element = document.getElementById(`field-row-${rowId}`);
      if (!element) return;
      element.scrollIntoView({ behavior: "smooth", block: "center" });
      element.classList.add("bg-primary/10");
      setTimeout(() => element.classList.remove("bg-primary/10"), 2000);
    });
  }

  function exportFieldsJson() {
    const fields = allRows
      .filter((row) => row.scalar)
      .map((row) => scalarToExportField(row.scalar!, row.correction));
    downloadReviewedJson(`${result.document_id}-fields.json`, fields);
  }

  function exportFieldsCsv() {
    const fields = allRows
      .filter((row) => row.scalar)
      .map((row) => scalarToExportField(row.scalar!, row.correction));
    // Wide business CSV: field keys as headers, one data row.
    const headers = fields.map((field) => field.field_key || field.field);
    const values = fields.map((field) => field.value ?? "");
    const escape = (cell: string) => {
      if (/[",\n]/.test(cell)) return `"${cell.replace(/"/g, '""')}"`;
      return cell;
    };
    const csv = `${headers.map(escape).join(",")}\n${values.map((v) => escape(String(v))).join(",")}\n`;
    downloadBlob(
      csv,
      `${result.document_id}-fields.csv`,
      "text/csv;charset=utf-8;",
    );
  }

  async function exportFieldsXlsx() {
    if (!documentId) return;
    try {
      await downloadDocumentExportXlsx(
        documentId,
        `${result.document_id}-export.xlsx`,
      );
    } catch {
      // Non-fatal if metadata fields were not persisted yet.
    }
  }

  return (
    <div className="space-y-6">
      <ResultSummaryBar
        documentName={documentName ?? "Document"}
        status={status}
        fieldsExtracted={result.scalars.length}
        tablesExtracted={dataTables.length}
        highConfidence={confidenceCounts.high}
        mediumConfidence={confidenceCounts.medium}
        lowConfidence={confidenceCounts.low}
        validationWarnings={issueCount}
        processingDurationMs={processingDurationMs}
      />

      {(dataTables.length > 0 || clauseTables.length > 0) && (
        <div className="flex gap-1 rounded-lg border border-border bg-surface-soft p-1">
          <button
            type="button"
            onClick={() => setActiveTab("fields")}
            className={[
              "flex-1 rounded-md px-3 py-1.5 text-sm font-semibold transition sm:flex-none",
              activeTab === "fields"
                ? "bg-surface text-primary shadow-sm"
                : "text-text-secondary",
            ].join(" ")}
          >
            Fields
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("tables")}
            className={[
              "flex-1 rounded-md px-3 py-1.5 text-sm font-semibold transition sm:flex-none",
              activeTab === "tables"
                ? "bg-surface text-primary shadow-sm"
                : "text-text-secondary",
            ].join(" ")}
          >
            Tables ({dataTables.length + clauseTables.length})
          </button>
        </div>
      )}

      {activeTab === "fields" && allRows.length > 0 && (
        <div className="space-y-2.5 rounded-xl border border-border bg-surface-soft p-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search fields or values..."
              className="w-full min-w-0 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-foreground outline-none placeholder:text-text-muted sm:w-auto sm:flex-1"
            />
            <select
              value={confidenceFilter}
              onChange={(event) =>
                setConfidenceFilter(
                  event.target.value as "all" | "high" | "medium" | "low",
                )
              }
              className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground outline-none"
            >
              <option value="all">All confidence</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select
              value={methodFilter}
              onChange={(event) => setMethodFilter(event.target.value)}
              className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground outline-none"
            >
              {METHOD_FILTER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={validationFilter}
              onChange={(event) =>
                setValidationFilter(event.target.value as "all" | FieldRowStatus)
              }
              className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground outline-none"
            >
              {VALIDATION_FILTER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <div className="relative ml-auto" ref={exportMenuRef}>
              <button
                type="button"
                onClick={() => setExportMenuOpen((open) => !open)}
                className="btn-secondary py-1.5 text-xs"
              >
                <Download className="h-3.5 w-3.5" />
                Export
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
              {exportMenuOpen && (
                <div className="absolute right-0 top-full z-10 mt-1 w-40 rounded-lg border border-border bg-surface p-1 shadow-lg">
                  <button
                    type="button"
                    onClick={() => {
                      exportFieldsJson();
                      setExportMenuOpen(false);
                    }}
                    className="block w-full rounded-md px-3 py-1.5 text-left text-xs text-foreground hover:bg-surface-soft"
                  >
                    Download JSON
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      exportFieldsCsv();
                      setExportMenuOpen(false);
                    }}
                    className="block w-full rounded-md px-3 py-1.5 text-left text-xs text-foreground hover:bg-surface-soft"
                  >
                    Download CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void exportFieldsXlsx();
                      setExportMenuOpen(false);
                    }}
                    className="block w-full rounded-md px-3 py-1.5 text-left text-xs text-foreground hover:bg-surface-soft"
                  >
                    Export Excel (.xlsx)
                  </button>
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4 px-1">
            <label className="flex items-center gap-1.5 text-xs text-text-secondary">
              <input
                type="checkbox"
                checked={onlyWithValues}
                onChange={(event) => {
                  setOnlyWithValues(event.target.checked);
                  if (event.target.checked) setOnlyMissing(false);
                }}
              />
              Only fields with values
            </label>
            <label className="flex items-center gap-1.5 text-xs text-text-secondary">
              <input
                type="checkbox"
                checked={onlyMissing}
                onChange={(event) => {
                  setOnlyMissing(event.target.checked);
                  if (event.target.checked) setOnlyWithValues(false);
                }}
              />
              Only missing fields
            </label>
          </div>
        </div>
      )}

      {activeTab === "fields" && internalMissingCount > 0 && (
        <p className="text-xs text-text-muted">
          {internalMissingCount} internal form field
          {internalMissingCount === 1 ? " was" : "s were"} skipped (no
          readable value could be mapped).
        </p>
      )}

      {activeTab === "fields" && allRows.length > 0 && filteredRows.length === 0 && (
        <p className="rounded-xl border border-border bg-surface-soft p-4 text-center text-sm text-text-secondary">
          No fields match the current search/filter.
        </p>
      )}

      <div
        id="fields-section"
        className={["space-y-6", activeTab === "fields" ? "" : "hidden"].join(" ")}
      >
        <FieldsDatasetTable
          rows={filteredRows.length > 0 ? filteredRows : fieldRows}
          selectedId={selectedResultId}
        />
        <FieldsTable
          title="Field details & review"
          rows={fieldRows}
          selectedId={selectedResultId}
          onViewSource={onViewSource}
          onSaveCorrection={documentId ? handleSaveCorrection : undefined}
          onMarkVerified={documentId ? handleMarkVerified : undefined}
          onReject={documentId ? handleReject : undefined}
        />
        <FieldsTable
          title="Identifiers & codes"
          rows={identifierRows}
          selectedId={selectedResultId}
          onViewSource={onViewSource}
          onSaveCorrection={documentId ? handleSaveCorrection : undefined}
          onMarkVerified={documentId ? handleMarkVerified : undefined}
          onReject={documentId ? handleReject : undefined}
        />
        <FieldsTable
          title="Contacts"
          rows={contactRows}
          selectedId={selectedResultId}
          onViewSource={onViewSource}
          onSaveCorrection={documentId ? handleSaveCorrection : undefined}
          onMarkVerified={documentId ? handleMarkVerified : undefined}
          onReject={documentId ? handleReject : undefined}
        />
      </div>

      {activeTab === "tables" && dataTables.length > 0 && (
        <div id="tables-section">
          <h3 className="mb-3 text-sm font-semibold text-foreground">Tables</h3>
          <div className="space-y-4">
            {dataTables.map((table, index) => (
              <TableResult
                key={tableToUniversalTable(table, index).table_id}
                table={tableToUniversalTable(table, index)}
                onViewSource={
                  onViewSource
                    ? (req) =>
                        onViewSource({
                          ...req,
                          id: tableToUniversalTable(table, index).table_id,
                          value: table.target,
                          verified: true,
                        })
                    : undefined
                }
              />
            ))}
          </div>
        </div>
      )}

      {activeTab === "tables" && clauseTables.length > 0 && (
        <div className="editorial-card p-5 sm:p-6">
          <h3 className="text-sm font-semibold text-foreground">
            Clauses & sections
          </h3>
          <div className="mt-3 space-y-2">
            {clauseTables.map((table, index) => {
              const pages = table.pages.length
                ? `Pages ${table.pages.join(", ")}`
                : "Source pending";
              const preview =
                table.rows[0] && table.columns[0]
                  ? String(table.rows[0][table.columns[0]] ?? "")
                  : "";

              return (
                <details
                  key={`${table.target}-${index}`}
                  className="group rounded-xl border border-border bg-surface-soft"
                >
                  <summary className="cursor-pointer list-none px-4 py-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-foreground">
                          {table.target}
                        </p>
                        <p className="mt-0.5 text-xs text-text-secondary">
                          {pages}
                          {table.rows.length > 0 &&
                            ` · ${table.rows.length} row${table.rows.length === 1 ? "" : "s"}`}
                        </p>
                        {preview && (
                          <p className="mt-2 line-clamp-2 text-sm leading-5 text-text-secondary">
                            {preview}
                          </p>
                        )}
                      </div>
                      <span className="inline-flex items-center rounded-full bg-success/10 px-2.5 py-1 text-[11px] font-semibold text-success">
                        Source verified
                      </span>
                    </div>
                  </summary>
                  <div className="border-t border-border p-3">
                    <TableResult
                      table={tableToUniversalTable(table, index + 1000)}
                    />
                  </div>
                </details>
              );
            })}
          </div>
        </div>
      )}

      {activeTab === "fields" && (
        <div id="validation-section">
          <h3 className="mb-3 text-sm font-semibold text-foreground">
            Validation Issues
          </h3>
          <ValidationIssuesPanel rows={allRows} onIssueClick={handleIssueClick} />
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="rounded-xl border border-border bg-surface-soft p-4 text-xs text-text-secondary">
          {result.warnings.map((warning, index) => (
            <p key={index}>{warning}</p>
          ))}
        </div>
      )}
    </div>
  );
}
