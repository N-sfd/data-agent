import type {
  DetectedTarget,
  DetectionCounts,
  DetectionExtractionType,
} from "@/types/document";

export const DETECTION_TYPE_ORDER: DetectionExtractionType[] = [
  "table",
  "field",
  "contact",
  "obligation",
  "clause",
  "signature",
];

export const DETECTION_TYPE_LABELS: Record<DetectionExtractionType, string> = {
  field: "Field",
  table: "Table",
  contact: "Contacts",
  obligation: "Obligations",
  clause: "Clauses",
  signature: "Signatures",
  custom: "Custom",
};

export const DETECTION_TYPE_PLURAL: Record<DetectionExtractionType, string> = {
  field: "Fields",
  table: "Tables",
  contact: "Contacts",
  obligation: "Obligations",
  clause: "Clauses",
  signature: "Signatures",
  custom: "Custom",
};

export const DETECTION_COUNT_KEYS: Record<
  keyof DetectionCounts,
  DetectionExtractionType
> = {
  tables: "table",
  fields: "field",
  contacts: "contact",
  obligations: "obligation",
  clauses: "clause",
  signatures: "signature",
};

// A single option in the unified Extraction Target list. "named" and
// "grouped" come from real detection data; "template" is the generic
// starting-point library used as a fallback when nothing was
// detected for a type; "custom" is the free-form quick-pick library.
export interface UnifiedTargetOption {
  kind: "named" | "grouped" | "template" | "custom";
  type: DetectionExtractionType;
  key: string;
  label: string;
  prompt: string;
}

export interface PageGroup {
  page: number;
  count: number;
  keys: string[];
}

// Low-confidence, unlabeled detections (e.g. nine near-identical
// unheaded tables on page 11) collapse to one entry per page instead
// of flooding the UI with "Table (page 11)" repeated nine times.
export function groupByPage(
  targets: DetectedTarget[],
  extractionType: DetectionExtractionType,
): PageGroup[] {
  const byPage = new Map<number, PageGroup>();

  for (const target of targets) {
    if (target.extraction_type !== extractionType) continue;

    const pages = target.pages.length > 0 ? target.pages : [0];
    for (const page of pages) {
      const group = byPage.get(page) ?? { page, count: 0, keys: [] };
      group.count += 1;
      group.keys.push(target.key);
      byPage.set(page, group);
    }
  }

  return Array.from(byPage.values()).sort((a, b) => a.page - b.page);
}

export function pageGroupLabel(group: PageGroup, typeLabel: string): string {
  const singular = typeLabel.replace(/s$/, "");
  return group.count > 1
    ? `Page ${group.page} — ${group.count} ${typeLabel.toLowerCase()}`
    : `Page ${group.page} ${singular}`;
}

export function hasDetectionCounts(
  counts: DetectionCounts,
  tableTotal?: number,
): boolean {
  const tables = tableTotal ?? counts.tables;
  return (
    tables > 0 ||
    counts.fields > 0 ||
    counts.contacts > 0 ||
    counts.obligations > 0 ||
    counts.clauses > 0 ||
    counts.signatures > 0
  );
}

export function pageGroupPrompt(group: PageGroup, typeLabel: string): string {
  const noun = typeLabel.toLowerCase();
  const singular = noun.replace(/s$/, "");
  return group.count > 1
    ? `Extract all ${group.count} ${noun} on page ${group.page}.`
    : `Extract the ${singular} on page ${group.page}.`;
}
