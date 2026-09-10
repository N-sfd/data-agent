import type { DocumentTarget, TargetType } from "@/types/document";

export const TARGET_TYPE_ORDER: TargetType[] = [
  "field",
  "identifier",
  "date",
  "amount",
  "table",
  "section",
  "clause",
  "contact",
  "obligation",
  "signature",
];

const DISPLAY_GROUP_LABELS: Record<string, string> = {
  fields: "Fields",
  tables: "Tables",
  sections: "Sections",
  contacts: "Contacts",
  dates_amounts: "Dates & Amounts",
  identifiers: "Identifiers & Codes",
  clauses: "Clauses",
  obligations: "Obligations",
  signatures: "Signatures",
  custom: "Custom",
};

const TYPE_TO_GROUP_KEY: Record<TargetType, string> = {
  field: "fields",
  table: "tables",
  section: "sections",
  contact: "contacts",
  date: "dates_amounts",
  amount: "dates_amounts",
  identifier: "identifiers",
  clause: "clauses",
  obligation: "obligations",
  signature: "signatures",
  custom: "custom",
};

const GROUP_ORDER = [
  "fields",
  "identifiers",
  "dates_amounts",
  "tables",
  "sections",
  "clauses",
  "contacts",
  "obligations",
  "signatures",
  "custom",
];

export function displayGroup(type: TargetType): string {
  return TYPE_TO_GROUP_KEY[type] ?? "custom";
}

export function displayGroupLabel(groupKey: string): string {
  return DISPLAY_GROUP_LABELS[groupKey] ?? groupKey;
}

export function groupTargets(
  targets: DocumentTarget[],
): Map<string, DocumentTarget[]> {
  const groups = new Map<string, DocumentTarget[]>();

  for (const target of targets) {
    if (target.selectable === false || target.is_internal) {
      continue;
    }
    const key = target.group?.trim() || displayGroup(target.target_type);
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(target);
    } else {
      groups.set(key, [target]);
    }
  }

  const preferred = [
    "Solicitation Metadata",
    "Identifiers",
    "Dates",
    "Pricing",
    "Parties",
    "Contacts",
    "Addresses",
    "Tables",
    "Clauses",
    "Signatures",
    "Document Fields",
    "Custom Fields",
    ...GROUP_ORDER,
  ];

  const ordered = new Map<string, DocumentTarget[]>();
  for (const key of preferred) {
    const bucket = groups.get(key);
    if (bucket && bucket.length > 0) {
      ordered.set(
        key,
        [...bucket].sort((a, b) => b.confidence - a.confidence),
      );
    }
  }
  for (const [key, bucket] of groups) {
    if (!ordered.has(key) && bucket.length > 0) {
      ordered.set(
        key,
        [...bucket].sort((a, b) => b.confidence - a.confidence),
      );
    }
  }

  return ordered;
}

export function filterTargets(
  targets: DocumentTarget[],
  query: string,
): DocumentTarget[] {
  const trimmed = query.trim().toLowerCase();
  const visible = targets.filter(
    (target) => target.selectable !== false && !target.is_internal,
  );
  if (!trimmed) {
    return visible;
  }
  return visible.filter(
    (target) =>
      target.label.toLowerCase().includes(trimmed) ||
      target.key.toLowerCase().includes(trimmed) ||
      (target.group ?? "").toLowerCase().includes(trimmed) ||
      (target.source_labels ?? []).some((label) =>
        label.toLowerCase().includes(trimmed),
      ),
  );
}
