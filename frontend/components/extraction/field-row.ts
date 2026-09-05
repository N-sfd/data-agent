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

function statusForScalar(scalar: ScalarTargetResult): FieldRowStatus {
  if (isEmptyValue(scalar.value)) return "empty";
  if (!scalar.verified) return "validation_failed";
  if (scalar.confidence_band === "low") return "low_confidence";
  return "extracted";
}

export function buildFieldRows(
  scalars: ScalarTargetResult[],
  unresolvedTargets: { key: string; label: string }[],
  correctionsByKey: Map<string, TargetCorrection>,
): FieldRow[] {
  const resolved: FieldRow[] = scalars.map((scalar) => ({
    id: scalar.normalized_key,
    label: scalar.normalized_key,
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
