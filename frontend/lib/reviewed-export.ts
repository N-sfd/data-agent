import { apiFetch, fetchWithRetry } from "@/lib/api";
import { downloadBlob, downloadCsv, downloadJson, toCsv } from "@/lib/export";
import type { ScalarTargetResult, TargetCorrection } from "@/types/document";

/** Reviewed-value export row — mirrors backend `field_to_export_record`. */
export interface ReviewedExportField {
  field: string;
  field_key?: string;
  field_group?: string;
  extracted_value: string;
  value: string;
  review_status: string;
  confidence: number | null;
  validation: { status: string };
  source: { page: number | null };
  authoritative?: boolean;
}

export interface DocumentExportResponse {
  document_id: string;
  document_filename: string;
  generated_at: string;
  authoritative_only: boolean;
  field_count: number;
  fields: ReviewedExportField[];
  skipped: Array<{
    field: string;
    field_key: string;
    review_status: string;
    reason: string;
  }>;
}

export interface OraclePayloadPreview {
  document_id: string;
  source_document: string;
  erp_target: string;
  mode: string;
  dry_run: boolean;
  send_allowed: boolean;
  generated_at: string;
  excluded_statuses: string[];
  contract_header: Record<string, string>;
  fields: ReviewedExportField[];
  skipped: Array<{
    field: string;
    field_key: string;
    review_status: string;
    reason: string;
  }>;
  authoritative_count: number;
  skipped_count: number;
  ready_to_send: boolean;
}

const CSV_HEADERS = [
  "field",
  "value",
  "extracted_value",
  "review_status",
  "confidence",
  "validation_status",
  "source_page",
];

export function scalarToExportField(
  scalar: ScalarTargetResult,
  correction?: TargetCorrection | null,
): ReviewedExportField {
  const extracted =
    scalar.extracted_value != null && String(scalar.extracted_value) !== ""
      ? String(scalar.extracted_value)
      : String(scalar.value ?? "");

  let effective = String(scalar.value ?? "");
  let reviewStatus = scalar.review_status ?? "pending";

  if (correction?.action === "edit") {
    effective = String(correction.corrected_value ?? effective);
    reviewStatus = "edited";
  } else if (correction?.action === "verify") {
    reviewStatus = "accepted";
  } else if (correction?.action === "reject") {
    reviewStatus = "rejected";
  }

  return {
    field: scalar.target,
    field_key: scalar.normalized_key,
    extracted_value: extracted,
    value: effective,
    review_status: reviewStatus,
    confidence: scalar.confidence ?? null,
    validation: {
      status:
        scalar.validation?.status ??
        scalar.validation_status ??
        "passed",
    },
    source: {
      page: scalar.page ?? scalar.evidence?.page_number ?? null,
    },
    authoritative: reviewStatus === "accepted" || reviewStatus === "edited",
  };
}

export function exportFieldsToCsvRows(
  fields: ReviewedExportField[],
): Record<string, unknown>[] {
  return fields.map((row) => ({
    field: row.field,
    value: row.value,
    extracted_value: row.extracted_value,
    review_status: row.review_status,
    confidence: row.confidence ?? "",
    validation_status: row.validation.status,
    source_page: row.source.page ?? "",
  }));
}

export function downloadReviewedJson(
  filename: string,
  fields: ReviewedExportField[],
) {
  downloadJson(filename, fields);
}

export function downloadReviewedCsv(
  filename: string,
  fields: ReviewedExportField[],
) {
  downloadCsv(filename, CSV_HEADERS, exportFieldsToCsvRows(fields));
}

export function reviewedCsvString(fields: ReviewedExportField[]): string {
  return toCsv(CSV_HEADERS, exportFieldsToCsvRows(fields));
}

export async function getDocumentExport(
  documentId: string,
  options?: { authoritativeOnly?: boolean },
): Promise<DocumentExportResponse> {
  const query = options?.authoritativeOnly ? "?authoritative_only=true" : "";
  return apiFetch<DocumentExportResponse>(
    `/api/documents/${documentId}/export${query}`,
  );
}

export async function downloadDocumentExportCsv(
  documentId: string,
  filename: string,
  options?: { authoritativeOnly?: boolean },
): Promise<void> {
  const query = options?.authoritativeOnly ? "?authoritative_only=true" : "";
  const response = await fetchWithRetry(
    `/api/documents/${documentId}/export.csv${query}`,
    undefined,
  );
  if (!response.ok) {
    throw new Error(`Export CSV failed (${response.status})`);
  }
  const text = await response.text();
  downloadBlob(text, filename, "text/csv;charset=utf-8;");
}

export async function downloadDocumentExportLineItemsCsv(
  documentId: string,
  filename: string,
  options?: { tableKey?: string },
): Promise<void> {
  const query = options?.tableKey
    ? `?table_key=${encodeURIComponent(options.tableKey)}`
    : "";
  const response = await fetchWithRetry(
    `/api/documents/${documentId}/export/line-items.csv${query}`,
    undefined,
  );
  if (!response.ok) {
    throw new Error(`Export Line Items CSV failed (${response.status})`);
  }
  const text = await response.text();
  downloadBlob(text, filename, "text/csv;charset=utf-8;");
}

export async function downloadDocumentExportXlsx(
  documentId: string,
  filename: string,
  options?: { authoritativeOnly?: boolean },
): Promise<void> {
  const query = options?.authoritativeOnly ? "?authoritative_only=true" : "";
  const response = await fetchWithRetry(
    `/api/documents/${documentId}/export.xlsx${query}`,
    undefined,
  );
  if (!response.ok) {
    throw new Error(`Export Excel failed (${response.status})`);
  }
  const blob = await response.blob();
  downloadBlob(
    blob,
    filename.endsWith(".xlsx") ? filename : `${filename}.xlsx`,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  );
}

export async function getOraclePayloadPreview(
  documentId: string,
): Promise<OraclePayloadPreview> {
  return apiFetch<OraclePayloadPreview>(
    `/api/documents/${documentId}/oracle-payload`,
  );
}
