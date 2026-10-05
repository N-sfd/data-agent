import type { StagingColumn, StagingRecord } from "@/lib/staging-workbook";

/** Sizing and freezing for the shared staging data grid. Labels and column
 * order always come from the dataset (the source / profile); this only
 * decides how wide each column is and which leading columns stay frozen. */

export const MIN_COLUMN_WIDTH = 80;
export const MAX_COLUMN_WIDTH = 340;
const SAMPLE = 200;
const DATE = /^(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[- ][A-Za-z]{3,9}[- ]\d{2,4}|[A-Za-z]{3,9}\.? \d{1,2},? \d{4}|[A-Za-z]{3,9} \d{4})$/;

function text(value: unknown): string {
  return value == null ? "" : String(value).replace(/\s+/g, " ").trim();
}

/** A width that shows a typical value on one line: Y/N flags and codes
 * stay narrow, dates fit, prose gets a wide column (ellipsized). */
export function columnWidth(column: StagingColumn, records: StagingRecord[]): number {
  return Math.max(valueWidth(column, records), headerWordWidth(column.display_label));
}

/** Headers wrap only between words: a column is never narrower than its
 * longest header word (11px uppercase ≈ 7.5px per letter, plus padding). */
function headerWordWidth(label: string): number {
  const longest = Math.max(0, ...label.split(/[\s/]+/).map((word) => word.length));
  return Math.min(MAX_COLUMN_WIDTH, Math.round(longest * 7.5 + 26));
}

function valueWidth(column: StagingColumn, records: StagingRecord[]): number {
  const values: string[] = [];
  for (const record of records) {
    const value = text(record.cells[column.canonical_field]?.value);
    if (value) values.push(value);
    if (values.length >= SAMPLE) break;
  }
  const labelWidth = Math.min(column.display_label.length * 7 + 28, 170);
  if (values.length === 0) return clamp(Math.max(labelWidth, 100));
  if (values.every((value) => DATE.test(value))) return clamp(Math.max(115, Math.min(labelWidth, 140)));
  const average = values.reduce((sum, value) => sum + value.length, 0) / values.length;
  let width: number;
  if (average <= 4) width = 80;
  else if (average <= 10) width = 105;
  else if (average <= 18) width = 140;
  else if (average <= 30) width = 200;
  else if (average <= 60) width = 250;
  else if (average <= 120) width = 300;
  else width = MAX_COLUMN_WIDTH;
  // Short values keep their header readable; prose doesn't need to.
  return clamp(average <= 30 ? Math.max(width, Math.min(labelWidth, 150)) : width);
}

function clamp(width: number): number {
  return Math.max(MIN_COLUMN_WIDTH, Math.min(MAX_COLUMN_WIDTH, Math.round(width)));
}

const IDENTIFIER = /(^|\b)(number|no\.?|id|item no\.?|clin|code|clause number|reference|far number|record id|key)$/i;
const TITLE = /^(title|field \/ title|name|display name|field|description|supplies\/services)$/i;
/** Frozen columns never take more than this much of the grid's width. */
export const MAX_FROZEN_WIDTH = 640;

/** How many leading columns stay frozen on horizontal scroll: through the
 * record's identifier and, when it follows closely, its title — found by
 * the dataset's own column names, not by profile. Falls back to the first
 * column. */
export function frozenColumnCount(columns: StagingColumn[], widths: number[]): number {
  const labels = columns.map((column) => column.display_label.trim());
  const identifier = labels.findIndex((label, index) => index < 6 && IDENTIFIER.test(label));
  const title = labels.findIndex((label, index) => index < 7 && TITLE.test(label));
  const within = (count: number) => widths.slice(0, count).reduce((sum, width) => sum + width, 0) <= MAX_FROZEN_WIDTH;
  const candidates = [
    identifier >= 0 && title > identifier && title - identifier <= 2 ? title + 1 : -1,
    identifier >= 0 ? identifier + 1 : -1,
    title >= 0 ? title + 1 : -1,
  ];
  for (const count of candidates) {
    if (count > 0 && within(count)) return count;
  }
  return columns.length > 1 ? 1 : 0;
}

/** Left offsets (px) of the frozen columns. */
export function frozenOffsets(widths: number[], count: number): number[] {
  const offsets: number[] = [];
  let left = 0;
  for (let index = 0; index < count; index += 1) {
    offsets.push(left);
    left += widths[index];
  }
  return offsets;
}
