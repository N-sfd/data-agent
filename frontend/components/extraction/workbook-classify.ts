import type { FieldRow } from "@/components/extraction/field-row";
import type { DocumentTarget, TableTargetResult } from "@/types/document";

export type WorkbookTab =
  | "all"
  | "key"
  | "sections"
  | "line_items"
  | "tables"
  | "needs_review";

const KEY_CONTRACT_KEYS = new Set([
  "contract_number",
  "solicitation_number",
  "award_date",
  "contractor_name",
  "contractor",
  "ueid",
  "uei",
  "type_of_solicitation",
  "date_issued",
  "issued_by",
  "effective_date",
  "expiration_date",
  "total_value",
  "contract_value",
  "naics_code",
  "cage_code",
]);

const KEY_LABEL =
  /\b(contract\s*(no\.?|number|#)|solicitation|award\s*date|contractor|uei[d]?|type of solicitation|date issued|issued by|effective date|expiration|total\s*(value|amount)|naics|cage)\b/i;

const SECTION_HEADING =
  /^\s*(?:[A-Z]|\d{1,2})(?:\.\d{1,2})?\.?\s+(general|authority|background|scope|purpose|overview|introduction|requirements|summary)\b/i;

const SOW_KV =
  /^kv_[a-z](_\d+)?_(general|authority|scope|background|name|total_solution)$/i;

export function isAutoKvKey(key: string): boolean {
  return /^kv_/i.test(key.trim());
}

export function isNarrativeOrSectionRow(row: FieldRow): boolean {
  const key = row.id;
  const label = row.label || key;
  const value = row.value == null ? "" : String(row.value).trim();

  if (
    row.scalar?.normalized_key?.startsWith("section_") ||
    /^section_|clause_|article_/i.test(key)
  ) {
    return true;
  }
  if (SECTION_HEADING.test(label)) return true;
  if (isAutoKvKey(key)) {
    if (value.length >= 160) return true;
    if (SOW_KV.test(key) && (value.length >= 40 || !value)) return true;
  }
  return false;
}

export function isKeyContractRow(row: FieldRow): boolean {
  const key = row.id.toLowerCase();
  if (KEY_CONTRACT_KEYS.has(key)) return true;
  if (key.startsWith("kv_") && KEY_CONTRACT_KEYS.has(key.slice(3))) return true;
  return KEY_LABEL.test(`${row.id} ${row.label}`);
}

export function isBusinessFieldRow(row: FieldRow): boolean {
  return !isNarrativeOrSectionRow(row);
}

export function needsReviewRow(row: FieldRow): boolean {
  if (row.correction?.action === "reject") return true;
  if (row.status === "low_confidence" || row.status === "validation_failed") {
    return true;
  }
  if (row.status === "empty" || row.status === "not_found") return true;
  return false;
}

export function fieldTypeLabel(
  row: FieldRow,
  typeByLabel: Map<string, string>,
): string {
  const fromSchema =
    typeByLabel.get(row.scalar?.target.toLowerCase() ?? "") ??
    typeByLabel.get(row.label.toLowerCase());
  if (fromSchema === "contact") return "Contact";
  if (fromSchema === "identifier") return "Identifier";
  if (isKeyContractRow(row)) return "Key contract field";
  if (isNarrativeOrSectionRow(row)) return "Section";
  const section = (row.evidence?.section || "").toLowerCase();
  if (section.includes("sf33") || /sf[\s-]?33/i.test(row.label)) {
    return "SF33 field";
  }
  if (section.includes("award")) return "Award field";
  if (/^\d+[a-z]?\./i.test(row.label.trim())) return "Form field";
  return "Labeled value";
}

export function reviewStatusLabel(row: FieldRow): string {
  if (row.correction?.action === "reject") return "Rejected";
  if (row.correction?.action === "verify" || row.verified) return "Passed";
  if (row.correction?.action === "edit") return "Edited";
  if (row.status === "not_found" || row.status === "empty") return "Needs Review";
  if (row.status === "validation_failed" || row.status === "low_confidence") {
    return "Needs Review";
  }
  if (row.scalar?.validation_status === "passed" || row.status === "extracted") {
    return "Passed";
  }
  return "Needs Review";
}

export function isLineItemTable(table: TableTargetResult): boolean {
  const hay = `${table.target} ${table.columns.join(" ")}`.toLowerCase();
  return /\bclin\b|line\s*item|quantity|unit\s*price|extended|amount/.test(hay);
}

export function partitionWorkbookRows(
  rows: FieldRow[],
  typeByKey: Map<string, DocumentTarget>,
): Record<WorkbookTab, FieldRow[]> {
  const typeByLabel = new Map<string, string>();
  for (const target of typeByKey.values()) {
    typeByLabel.set(target.label.toLowerCase(), target.target_type);
    typeByLabel.set(target.key.toLowerCase(), target.target_type);
  }
  void typeByLabel;

  const all = rows.filter(isBusinessFieldRow);
  return {
    all,
    key: all.filter(isKeyContractRow),
    sections: rows.filter(isNarrativeOrSectionRow),
    line_items: [],
    tables: [],
    needs_review: all.filter(needsReviewRow),
  };
}
