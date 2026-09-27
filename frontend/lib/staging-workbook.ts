import { apiFetch, fetchWithRetry } from "@/lib/api";
import { downloadBlob } from "@/lib/export";

/** Mirrors backend app/staging/models.py. The UI renders any profile from
 * this shape alone — it never branches on a profile id. */

export type ReviewStatus = "Verified" | "Needs Review" | "Missing";

export interface SourceLocator {
  dom_path: string | null;
  element_id: string | null;
  section_path: string[];
  table_index: number | null;
  row_index: number | null;
  column_index: number | null;
  sheet_name: string | null;
  cell_ref: string | null;
}

export interface CellProvenance {
  source_document_id: string;
  source_filename: string;
  source_type: "pdf" | "image" | "html" | "docx" | "xlsx" | "text" | "system";
  source_page: number | null;
  source_bbox: [number, number, number, number] | null;
  evidence_text: string | null;
  extraction_method: string | null;
  source_locator: SourceLocator | null;
  source_region_id: string | null;
  anchor_text: string | null;
  highlight_text: string | null;
}

export interface ValidationCheck {
  check: string;
  passed: boolean;
  message: string | null;
}

/** Original table column a staged value came from (backend SourceColumn). */
export interface SourceColumn {
  raw_header: string | null;
  column_index: number;
  structural_role: string | null;
  structural_roles: string[];
}

export interface SourceColumnValue extends SourceColumn {
  raw_value: string;
  provenance: CellProvenance | null;
}

export interface StagingCell {
  canonical_field: string;
  display_label: string;
  value: string | number | boolean | null;
  raw_value: string | null;
  value_type: string;
  provenance: CellProvenance | null;
  validation: { status: "passed" | "failed" | "not_checked"; checks: ValidationCheck[] };
  review_status: ReviewStatus | null;
  review_reasons: string[];
  source_column?: SourceColumn | null;
}

export interface StagingRecord {
  record_id: string;
  cells: Record<string, StagingCell>;
  record_status: ReviewStatus | null;
  links_to_dataset: string | null;
  source_columns?: SourceColumnValue[];
}

export interface StagingColumn {
  canonical_field: string;
  key: string;
  display_label: string;
  value_type: string;
  expected: boolean;
}

export interface StagingDataset {
  dataset_id: string;
  display_name: string;
  cardinality: "single" | "repeating";
  role: "business" | "source" | "qa";
  description: string | null;
  columns: StagingColumn[];
  records: StagingRecord[];
  identity_fields: string[];
}

export interface ExportCapability {
  capability_id: string;
  label: string;
  format: "xlsx" | "csv" | "json" | "xml";
  href: string;
  dataset_id: string | null;
}

export interface ProfileDescriptor {
  profile_id: string;
  profile_version: number;
  display_name: string;
  description: string;
  document_families: string[];
  export_capabilities: ExportCapability[];
  oracle_mapping_capability: "planned" | "available" | "none";
}

export type OutcomeStatus =
  | "populated"
  | "needs_review"
  | "no_supported_fields"
  | "special_source"
  | "failed"
  | "pending";

export interface ExtractionOutcome {
  status: OutcomeStatus;
  title: string;
  message: string;
  details: string[];
  record_count: number;
  needs_review_count: number;
}

export interface QaSummary {
  verified: number;
  needs_review: number;
  missing: number;
  record_count: number;
}

export interface ProcessingMetadata {
  document_family: string | null;
  document_family_label: string | null;
  resolution_reasons: string[];
  resolved_at: string | null;
  page_count: number | null;
  source_type: CellProvenance["source_type"] | null;
  transcription_available: boolean;
}

export interface StagingWorkbook {
  document_id: string;
  document_filename: string;
  profile: ProfileDescriptor;
  outcome: ExtractionOutcome;
  datasets: StagingDataset[];
  qa_summary: QaSummary;
  processing_metadata: ProcessingMetadata;
}

export async function getStagingWorkbook(documentId: string): Promise<StagingWorkbook> {
  return apiFetch<StagingWorkbook>(`/api/documents/${documentId}/staging-workbook`);
}

export async function downloadExport(
  capability: ExportCapability,
  fallbackName: string,
): Promise<void> {
  const response = await fetchWithRetry(capability.href, undefined);
  if (!response.ok) {
    throw new Error(`${capability.label} failed (${response.status})`);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename =
    /filename="([^"]+)"/.exec(disposition)?.[1] ?? `${fallbackName}.${capability.format}`;
  if (capability.format === "csv") {
    downloadBlob(await response.text(), filename, "text/csv;charset=utf-8;");
    return;
  }
  downloadBlob(
    await response.blob(),
    filename,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  );
}

/** Mirrors backend app/source_structure/models.py (the subset the HTML
 * evidence view reads). */
export interface StructureTableCell {
  row_index: number;
  column_index: number;
  text: string;
  source_locator: SourceLocator | null;
}

export interface StructureTable {
  candidate_id: string;
  headers: string[];
  rows: StructureTableCell[][];
  source_locator: SourceLocator | null;
  detection_method: string;
}

export interface StructureField {
  raw_label: string;
  raw_value: string;
  label_text: string;
  structural_relation: string;
  evidence_text: string;
  source_locator: SourceLocator | null;
}

export interface StructureRegion {
  region_id: string;
  region_type: string;
  text: string;
  source_locator: SourceLocator | null;
}

export interface RegionContext {
  region: StructureRegion | null;
  field: StructureField | null;
  table: StructureTable | null;
  row_index: number | null;
  column_index: number | null;
}

export async function getRegionContext(
  documentId: string,
  regionId: string,
): Promise<RegionContext> {
  return apiFetch<RegionContext>(
    `/api/documents/${documentId}/source-structure/regions/${encodeURIComponent(regionId)}`,
  );
}
