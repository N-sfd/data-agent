import type { ReviewStatus, StagingDataset, StagingRecord } from "@/lib/staging-workbook";

/** FAR Clauses & Provisions (far_part_52 `far_records`): the grid's columns
 * in the specified order, with their widths (px). */
export const FAR_COLUMNS: { key: string; label: string; width: number }[] = [
  { key: "far_number", label: "FAR Number", width: 95 },
  { key: "title", label: "Title", width: 240 },
  { key: "record_type", label: "Record Type", width: 90 },
  { key: "far_part", label: "FAR Part", width: 80 },
  { key: "far_part_title", label: "FAR Part Title", width: 200 },
  { key: "far_subpart", label: "FAR Subpart", width: 100 },
  { key: "far_subpart_title", label: "FAR Subpart Title", width: 200 },
  { key: "far_section", label: "FAR Section", width: 95 },
  { key: "record_status", label: "Record Status", width: 90 },
  { key: "revision_date", label: "Revision Date", width: 95 },
  { key: "description", label: "Description", width: 220 },
  { key: "prescription", label: "Prescription / Usage", width: 240 },
  { key: "prescription_reference", label: "Prescription Reference", width: 130 },
  { key: "alternate", label: "Alternate", width: 150 },
  { key: "form_number", label: "Form Number", width: 110 },
  { key: "form_name", label: "Form Name", width: 220 },
  { key: "form_type", label: "Form Type", width: 120 },
  { key: "prescribing_reference", label: "Prescribing FAR Reference", width: 150 },
  { key: "form_usage", label: "Form Usage", width: 240 },
  { key: "supersession", label: "Replacement / Supersession", width: 200 },
  { key: "cross_references", label: "Cross References", width: 180 },
  { key: "provision_text", label: "Provision Text", width: 260 },
  { key: "clause_text", label: "Clause Text", width: 260 },
  { key: "section_text", label: "Section Text", width: 260 },
  { key: "source_reference", label: "Source Reference", width: 220 },
];

/** Columns frozen on horizontal scroll (FAR Number, Title). */
export const FROZEN_COLUMNS = 2;

/** The grid's columns for this source: a column no record (nor any of its
 * alternates) fills is left out — a policy Part has no prescriptions,
 * revision dates or alternates. The frozen columns always stay. */
export function visibleFarColumns(groups: FarGroup[], labels: Record<string, string> = {}): typeof FAR_COLUMNS {
  return FAR_COLUMNS.filter(
    (column, index) =>
      index < FROZEN_COLUMNS ||
      groups.some((group) => [group.record, ...group.alternates].some((record) => farValue(record, column.key))),
  ).map((column) => ({ ...column, label: labels[column.key] ?? column.label }));
}

/** The dataset's own column labels by key ("Description / Regulatory Text"
 * for a section's text outside Part 52). */
export function farColumnLabels(columns: { key: string; display_label: string }[]): Record<string, string> {
  return Object.fromEntries(columns.map((column) => [column.key, column.display_label]));
}

/** A record's own text and the column it is in (Clause, Provision or Section Text). */
export function farText(record: StagingRecord, labels: Record<string, string> = {}): { label: string; text: string } | null {
  for (const [key, label] of [
    ["clause_text", "Clause Text"],
    ["provision_text", "Provision Text"],
    ["section_text", "Section Text"],
  ]) {
    const text = farValue(record, key);
    if (text) return { label: labels[key] ?? label, text };
  }
  return null;
}

export function farValue(record: StagingRecord, key: string): string {
  const value = record.cells[`far.record.${key}`]?.value;
  return value == null ? "" : String(value);
}

/** One FAR record with the alternates the source places inside it. */
export interface FarGroup {
  record: StagingRecord;
  alternates: StagingRecord[];
  /** Needs Review when the record or any of its alternates does. */
  status: ReviewStatus | null;
}

/** Alternates belong to their basic FAR record (the source prints them
 * inside its article): each joins the closest preceding record with the
 * same FAR Number. One with no such record stays its own row. */
export function groupFarRecords(records: StagingRecord[]): FarGroup[] {
  const groups: FarGroup[] = [];
  const byNumber = new Map<string, FarGroup>();
  for (const record of records) {
    const number = farValue(record, "far_number");
    const parent = farValue(record, "alternate") ? byNumber.get(number) : undefined;
    if (parent) {
      parent.alternates.push(record);
      continue;
    }
    const group: FarGroup = { record, alternates: [], status: null };
    groups.push(group);
    byNumber.set(number, group);
  }
  for (const group of groups) {
    const statuses = [group.record, ...group.alternates].map((record) => record.record_status);
    group.status = statuses.includes("Needs Review")
      ? "Needs Review"
      : (group.record.record_status ?? (statuses.includes("Verified") ? "Verified" : null));
  }
  return groups;
}

/** The Alternate column of a grouped record: its alternates, in order. */
export function alternateSummary(group: FarGroup): string {
  if (group.alternates.length === 0) return farValue(group.record, "alternate");
  return group.alternates.map((alternate) => farValue(alternate, "alternate")).filter(Boolean).join("; ");
}

export type ReviewFilter = "all" | "Verified" | "Needs Review";

export function filterFarGroups(
  groups: FarGroup[],
  { query, type, review }: { query: string; type: string; review: ReviewFilter },
): FarGroup[] {
  const needle = query.trim().toLowerCase();
  return groups.filter((group) => {
    if (type !== "all" && farValue(group.record, "record_type") !== type) return false;
    if (review !== "all" && group.status !== review) return false;
    if (!needle) return true;
    return [group.record, ...group.alternates].some((record) =>
      Object.values(record.cells).some((cell) => String(cell.value ?? "").toLowerCase().includes(needle)),
    );
  });
}

/** Record types with counts, most common first. */
export function farTypeCounts(groups: FarGroup[]): { type: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const group of groups) {
    const type = farValue(group.record, "record_type");
    if (type) counts.set(type, (counts.get(type) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([type, count]) => ({ type, count }));
}

/** "Part 52 - Solicitation Provisions and Contract Clauses" ->
 * "FAR Part 52 — Solicitation Provisions and Contract Clauses". */
export function farHeading(partHeading: string | null | undefined): string {
  const text = (partHeading ?? "").trim();
  if (!text) return "FAR Clauses & Provisions";
  return `FAR ${text.replace(/\s+[-–—]\s+/, " — ")}`;
}

/** A FAR dataset without the grid columns no record fills (a policy Part
 * leaves the clause-library columns of Oracle Output empty). */
export function withoutBlankColumns(dataset: StagingDataset): StagingDataset {
  const fields = dataset.grid_fields?.length ? dataset.grid_fields : dataset.columns.map((column) => column.canonical_field);
  const filled = fields.filter((field) =>
    dataset.records.some((record) => {
      const value = record.cells[field]?.value;
      return value != null && String(value).trim() !== "";
    }),
  );
  if (dataset.records.length === 0 || filled.length === fields.length) return dataset;
  return { ...dataset, grid_fields: filled };
}
