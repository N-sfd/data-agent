import { apiFetch, fetchWithRetry } from "@/lib/api";
import { downloadBlob } from "@/lib/export";

/** Mirrors backend app/schemas/v3_document.py exactly — column names match
 * the ground-truth V3 workbook (docs/v3-schema-manifest.md). */

export interface V3AllFieldsRow {
  category: string;
  normalized_field: string;
  value: string;
  source_file: string;
  source_page: number;
  evidence: string;
  extraction_method: string;
  qa_status: string;
}

export interface V3ClinRow {
  clin: string;
  option_base: string | null;
  description: string | null;
  pricing_type: string | null;
  max_quantity: string | null;
  unit: string | null;
  unit_price: number | null;
  max_amount: number | null;
  status: string | null;
  fob: string | null;
  purchase_request: string | null;
  psc: string | null;
  pop_start: string | null;
  pop_end: string | null;
  ship_to: string | null;
  dodaac: string | null;
  source_page: number | null;
  evidence: string | null;
  qa_status: string | null;
}

export interface V3FundingRow {
  funding_level: string | null;
  clin: string | null;
  funding_status: string | null;
  amount: number | null;
  accounting_appropriation: string | null;
  purchase_request: string | null;
  source_page: number | null;
  evidence: string | null;
  qa_status: string | null;
}

export interface V3PerformanceDeliveryRow {
  record_type: string | null;
  clin: string | null;
  start: string | null;
  end_timing: string | null;
  location_destination: string | null;
  requirement: string | null;
  source_page: number | null;
  evidence: string | null;
  qa_status: string | null;
}

export interface V3AttachmentRow {
  attachment_reference: string;
  title_description: string | null;
  included_in_portfolio: string | null;
  source_page: number | null;
  evidence: string | null;
  qa_status: string | null;
}

export interface V3ClauseRow {
  regulation: string;
  clause_number: string;
  clause_title: string | null;
  alternate_deviation: string | null;
  effective_date: string | null;
  incorporation_type: string | null;
  source_page: number | null;
  evidence: string | null;
  qa_status: string | null;
}

export interface V3FarReferenceRow {
  far_reference: string;
  reference_type: string | null;
  subject_context: string | null;
  source_page: number | null;
  evidence: string | null;
  contract_clause: string | null;
  qa_status: string | null;
}

export interface V3SourceDocumentRow {
  source_document: string;
  role: string;
  pages: number;
  extraction_status: string;
}

export interface V3QaReviewRow {
  qa_check: string;
  result: string;
  details: string;
  action: string;
}

export interface V3ContractSummaryRow {
  contract_number: string | null;
  solicitation_rfp: string | null;
  contract_vehicle: string | null;
  agency_office: string | null;
  contractor: string | null;
  award_date: string | null;
  ceiling_max_aggregate: string | null;
  minimum_guarantee: string | null;
  base_period: string | null;
  options: string | null;
  max_duration: string | null;
  task_order_range: string | null;
  naics: string | null;
  size_standard: string | null;
  source_file: string | null;
  source_page: number | null;
  evidence: string | null;
  qa_status: string | null;
}

export interface NormalizedV3Document {
  document_id: string;
  document_filename: string;
  all_fields: V3AllFieldsRow[];
  clins: V3ClinRow[];
  funding: V3FundingRow[];
  performance_delivery: V3PerformanceDeliveryRow[];
  attachments: V3AttachmentRow[];
  clauses: V3ClauseRow[];
  far_references: V3FarReferenceRow[];
  dfars: V3ClauseRow[];
  source_documents: V3SourceDocumentRow[];
  qa_review: V3QaReviewRow[];
  contract_summary: V3ContractSummaryRow | null;
}

export async function getNormalizedV3Document(
  documentId: string,
): Promise<NormalizedV3Document> {
  return apiFetch<NormalizedV3Document>(`/api/documents/${documentId}/v3`);
}

export async function downloadV3DatasetCsv(
  documentId: string,
  dataset: string,
): Promise<void> {
  const response = await fetchWithRetry(
    `/api/documents/${documentId}/v3/${dataset}.csv`,
    undefined,
  );
  if (!response.ok) {
    throw new Error(`V3 ${dataset} CSV export failed (${response.status})`);
  }
  const text = await response.text();
  downloadBlob(text, `${dataset}.csv`, "text/csv;charset=utf-8;");
}

export async function downloadV3ExportXlsx(
  documentId: string,
  filename: string,
): Promise<void> {
  const response = await fetchWithRetry(
    `/api/documents/${documentId}/v3/export.xlsx`,
    undefined,
  );
  if (!response.ok) {
    throw new Error(`V3 Complete Excel export failed (${response.status})`);
  }
  const blob = await response.blob();
  downloadBlob(
    blob,
    filename.endsWith(".xlsx") ? filename : `${filename}.xlsx`,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  );
}
