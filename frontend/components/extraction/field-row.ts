import type {
  ConfidenceBand,
  ScalarTargetResult,
  SourceEvidence,
  TargetCorrection,
  TargetType,
} from "@/types/document";

export type FieldRowStatus =
  | "extracted"
  | "empty"
  | "low_confidence"
  | "validation_failed"
  | "not_found";

export interface FieldRow {
  /** Stable identity — normalized_key for resolved scalars, the raw
   * target key for unresolved ones. Used for filtering, DOM ids, and
   * matching corrections. */
  id: string;
  label: string;
  status: FieldRowStatus;
  value: unknown;
  confidence: number | null;
  confidence_band: ConfidenceBand | null;
  extraction_method: string | null;
  display_method: string | null;
  evidence: SourceEvidence | null;
  verified: boolean;
  correction: TargetCorrection | null;
  scalar: ScalarTargetResult | null;
}

function isEmptyValue(value: unknown): boolean {
  return value === null || value === undefined || String(value).trim() === "";
}

const INTERNAL_KEY_PREFIXES = ["kv_", "custom_", "section_", "table_", "field_"];
const ACRONYM_WORDS = new Set([
  "pr", "id", "uei", "ueid", "cage", "naics", "psc", "sow", "pws",
  "clin", "duns", "ssn", "ein", "po", "rfq", "rfp", "far", "dfars",
]);

/** Last-resort display text — never surfaces a raw discovery candidate
 * key (e.g. "kv_pricing_arrangement") verbatim in the UI. */
function humanizeFieldKey(key: string): string {
  let text = (key || "").trim();
  if (!text) return "Untitled Field";
  const lowered = text.toLowerCase();
  const prefix = INTERNAL_KEY_PREFIXES.find((p) => lowered.startsWith(p));
  if (prefix) text = text.slice(prefix.length);
  const words = text.split(/[_\s]+/).filter(Boolean);
  if (words.length === 0) return "Untitled Field";
  return words
    .map((word) =>
      ACRONYM_WORDS.has(word.toLowerCase())
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1).toLowerCase(),
    )
    .join(" ");
}

/** ScalarTargetResult.target is the discovery candidate's internal key,
 * not a display label — resolve the real label from the discovered
 * target list, falling back to a humanized key rather than ever
 * rendering a raw "kv_*" candidate key in the UI. */
function displayLabelFor(
  scalar: ScalarTargetResult,
  labelByKey?: Map<string, string>,
): string {
  const fromSchema = labelByKey?.get(scalar.normalized_key);
  if (fromSchema) return fromSchema;
  const target = (scalar.target || "").trim();
  if (target && target !== scalar.normalized_key && !/^(kv|custom)_/i.test(target)) {
    return target;
  }
  return humanizeFieldKey(scalar.normalized_key);
}

function statusForScalar(scalar: ScalarTargetResult): FieldRowStatus {
  if (isEmptyValue(scalar.value)) return "empty";
  if (scalar.validation_status === "failed" || !scalar.verified) {
    return "validation_failed";
  }
  if (scalar.confidence_band === "low") return "low_confidence";
  return "extracted";
}

export function buildFieldRows(
  scalars: ScalarTargetResult[],
  unresolvedTargets: { key: string; label: string }[],
  correctionsByKey: Map<string, TargetCorrection>,
  labelByKey?: Map<string, string>,
): FieldRow[] {
  const resolved: FieldRow[] = scalars.map((scalar) => ({
    id: scalar.normalized_key,
    label: displayLabelFor(scalar, labelByKey),
    status: statusForScalar(scalar),
    value: scalar.value,
    confidence: scalar.confidence,
    confidence_band: scalar.confidence_band,
    extraction_method: scalar.extraction_method,
    display_method: scalar.display_method,
    evidence: scalar.evidence,
    verified: scalar.verified,
    correction: correctionsByKey.get(scalar.normalized_key) ?? null,
    scalar,
  }));

  const missing: FieldRow[] = unresolvedTargets.map(({ key, label }) => ({
    id: key,
    label,
    status: "not_found",
    value: null,
    confidence: null,
    confidence_band: null,
    extraction_method: null,
    display_method: null,
    evidence: null,
    verified: false,
    correction: null,
    scalar: null,
  }));

  return [...resolved, ...missing];
}

export function classifyRowKind(
  row: FieldRow,
  typeByLabel: Map<string, TargetType>,
): "contact" | "identifier" | "field" {
  const fromSchema =
    typeByLabel.get(row.scalar?.target.toLowerCase() ?? "") ??
    typeByLabel.get(row.label.toLowerCase());

  if (fromSchema === "contact") return "contact";
  if (fromSchema === "identifier") return "identifier";

  const label = `${row.scalar?.target ?? ""} ${row.label}`.toLowerCase();
  if (
    /email|phone|contact|fax|address|name|signatory|officer|poc|point of contact/.test(
      label,
    )
  ) {
    return "contact";
  }
  if (
    /identifier|id\b|number|code|clin|cage|uei|duns|solicitation|contract no/.test(
      label,
    )
  ) {
    return "identifier";
  }
  return "field";
}

export const FIELD_ROW_STATUS_LABEL: Record<FieldRowStatus, string> = {
  extracted: "Extracted",
  empty: "Empty",
  low_confidence: "Needs review",
  validation_failed: "Unverified",
  not_found: "Not found",
};
