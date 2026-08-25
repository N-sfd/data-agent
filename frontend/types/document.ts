export interface ExistingDocumentSummary {
  document_id: string;
  original_filename: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface UploadedDocument {
  document_id: string;
  original_filename: string;
  status: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string | null;
  page_count: number;
  encrypted: boolean;
  uploaded_at: string;
  message: string;
  duplicate?: boolean;
  existing_document?: ExistingDocumentSummary | null;
  embedded_files?: EmbeddedFileSummary[] | null;
  pipeline_log?: string[];
  approved_by?: string | null;
  approved_at?: string | null;
  promoted_by?: string | null;
  promoted_at?: string | null;
}

export type DuplicateResolution = "use_existing" | "upload_anyway";

export type DocumentStatus =
  | "processing"
  | "review_required"
  | "completed";

export type RepositoryStatus =
  | "not_approved"
  | "approved"
  | "repository";

export interface DocumentSummary {
  document_id: string;
  original_filename: string;
  document_type: string | null;
  status: DocumentStatus;
  confidence: number | null;
  uploaded_at: string;
  page_count: number;
  fields_extracted: number;
  last_updated: string;
  counterparty?: string | null;
  effective_date?: string | null;
  expiration_date?: string | null;
  contract_value?: string | null;
  relationship?: string | null;
  repository_status?: RepositoryStatus;
}

export interface HierarchyNode {
  document_id: string;
  title: string;
  document_number: string | null;
  document_type: string | null;
  relationship_type: string | null;
  relationship_status: string | null;
  children: HierarchyNode[];
}

export interface DocumentHierarchyResult {
  roots: HierarchyNode[];
}

export interface DashboardStats {
  total_documents: number;
  completed: number;
  review_required: number;
  processing: number;
  extraction_accuracy: number | null;
  average_processing_seconds: number | null;
  human_review_rate: number | null;
  fields_extracted: number;
  review_completion_rate: number | null;
  ocr_accuracy: number | null;
  clause_extraction_accuracy: number | null;
  fields_extracted_today: number;
  documents_requiring_manual_review: number;
}

export type ReviewQueueBucket =
  | "high"
  | "medium"
  | "low"
  | "rejected"
  | "unknown";

export interface ReviewQueueEntry {
  document_id: string;
  original_filename: string;
  document_type: string | null;
  confidence: number | null;
  queue_bucket: ReviewQueueBucket;
  uploaded_at: string;
}

export interface DocumentSearchResponse {
  documents: DocumentSummary[];
  total: number;
}

export interface GlobalAuditEntry {
  document_id: string;
  document_filename: string;
  field_key: string;
  action: ReviewAction;
  previous_value: string | null;
  new_value: string | null;
  changed_by: string;
  changed_at: string;
}

export interface GlobalAuditLogResponse {
  entries: GlobalAuditEntry[];
  total: number;
}

export interface ExtractionProgress {
  document_id: string;
  status: string;

  page_current: number;
  page_total: number;
  percent: number;

  native_pages: number;
  ocr_pages: number;
  ocr_completed_pages: number;
}

export interface DetectedTable {
  key: string;
  label: string;
  pages: number[];
  confidence: number;
  suggested_prompt?: string | null;
  columns?: string[];
}

export interface DetectedField {
  key: string;
  label: string;
  pages: number[];
}

export type DetectionExtractionType =
  | "field"
  | "table"
  | "contact"
  | "obligation"
  | "clause"
  | "signature"
  | "custom";

export interface DetectedTarget {
  key: string;
  label: string;
  extraction_type: DetectionExtractionType;
  pages: number[];
  confidence: number;
  evidence: string[];
  suggested_prompt: string | null;
  columns: string[];
}

export interface DetectionCounts {
  fields: number;
  tables: number;
  contacts: number;
  obligations: number;
  clauses: number;
  signatures: number;
}

export interface ContentStats {
  tables: number;
  dates: number;
  currency_values: number;
  organizations: number;
}

export type TargetType =
  | "field"
  | "table"
  | "section"
  | "contact"
  | "date"
  | "amount"
  | "identifier"
  | "clause"
  | "obligation"
  | "signature"
  | "custom";

export type TargetSource = "detected" | "template" | "custom";

export interface DocumentTarget {
  id: string;
  key: string;
  label: string;
  target_type: TargetType;
  page_numbers: number[];
  confidence: number;
  source_examples: string[];
  parent_section: string | null;
  columns: string[];
  occurrence_count: number;
  suggested_instruction: string | null;
  source: TargetSource;
}

export interface DiscoverSchemaResult {
  document_id: string;
  document_family: string;
  document_family_label: string;
  document_family_confidence: number;
  targets: DocumentTarget[];
  counts_by_type: Partial<Record<TargetType, number>>;
  generated_at: string;
}

export interface ScalarTargetResult {
  target: string;
  normalized_key: string;
  value: unknown;
  page: number;
  confidence: number;
  verified: boolean;
  extraction_method: string;
  evidence: SourceEvidence;
}

export interface TableTargetResult {
  target: string;
  columns: string[];
  rows: Record<string, unknown>[];
  pages: number[];
}

export interface ExtractTargetsResult {
  document_id: string;
  scalars: ScalarTargetResult[];
  tables: TableTargetResult[];
  unresolved_targets: string[];
  warnings: string[];
}

export interface EmbeddedFileSummary {
  filename: string;
  size_bytes: number;
}

export interface StructureDetectionResult {
  document_id: string;

  document_family: string;
  document_family_label: string;
  document_family_confidence: number;

  detected_fields: DetectedField[];
  detected_tables: DetectedTable[];
  detected_contacts: string[];
  detected_obligations: string[];

  detected_targets: DetectedTarget[];
  possible_targets: DetectedTarget[];

  content_stats: ContentStats;
  counts: DetectionCounts;
}

export interface ExtractionSummary {
  document_id: string;
  status: string;

  total_document_pages: number;
  pages_requested: number;
  pages_processed: number;

  native_pages: number;
  ocr_required_pages: number;
  ocr_completed_pages: number;
  failed_pages: number;

  page_numbers_processed: number[];
  warnings: string[];

  completed_at: string;
}

export interface DocumentPage {
  document_id: string;
  page_number: number;
  page_label: string | null;

  extraction_method: string;
  final_text: string;

  requires_ocr: boolean;
  ocr_attempted: boolean;
  ocr_succeeded: boolean;

  character_count: number;
  word_count: number;

  page_width: number;
  page_height: number;

  source_reference: string;
}

export interface FinancialTable {
  table_id: string;
  page_number: number;
  headers: string[];

  rows: Record<
    string,
    string | number | null
  >[];

  confidence: number;

  source_reference: string;

  warnings: string[];
}

export interface FinancialAnalysisResult {
  document_id: string;

  instruction: string;

  pages_used: number[];

  tables: FinancialTable[];

  status: string;

  warnings: string[];
}

export interface SourceEvidence {
  page_number: number;
  source_text: string;
  source_reference: string;

  section?: string | null;

  block_index?: number | null;

  x0?: number | null;
  y0?: number | null;
  x1?: number | null;
  y1?: number | null;
}

export interface UniversalValue {
  label: string;

  value: unknown;

  value_type: string;

  normalized_value?: unknown;

  confidence: number;

  extraction_method: string;

  evidence: SourceEvidence;

  verified: boolean;
}

export interface UniversalTable {
  table_id: string;

  title?: string | null;

  headers: string[];

  rows: Record<
    string,
    unknown
  >[];

  page_number: number;

  confidence: number;

  source_reference: string;
}

export interface UniversalExtractionResult {
  document_id: string;

  instruction: string;

  intent: string;

  answer?: string | null;

  values: UniversalValue[];

  tables: UniversalTable[];

  pages_used: number[];

  unresolved_requests: string[];

  warnings: string[];
}

export type ContractSide = "buy_side" | "sell_side" | "unknown";

export type DocumentStatusLabel =
  | "Original"
  | "Amendment"
  | "Renewal"
  | "Supporting Document"
  | "Unknown";

export const DOCUMENT_TYPE_OPTIONS = [
  "Master Services Agreement",
  "NDA",
  "Supplier Agreement",
  "Purchase Agreement",
  "Professional Services Agreement",
  "Software Agreement",
  "SaaS Agreement",
  "Lease",
  "Statement of Work",
  "Amendment",
  "Change Order",
  "Purchase Order",
  "Service Level Agreement",
  "License Agreement",
  "Consulting Agreement",
  "Construction Agreement",
  "Government Contract",
  "Subcontract",
  "Other",
] as const;

export interface ContractClassification {
  document_type: string;
  industry: string | null;
  contract_side: ContractSide;
  language: string | null;
  document_status: DocumentStatusLabel;
  confidence: number;
}

export interface ClassificationUpdate {
  document_type?: string;
  contract_side?: ContractSide;
  language?: string;
  changed_by: string;
}

export interface ClassificationHistoryEntry {
  field_changed: string;
  previous_value: string | null;
  new_value: string | null;
  changed_by: string;
  changed_at: string;
}

export type ReviewStatus =
  | "pending"
  | "accepted"
  | "edited"
  | "rejected"
  | "unknown";

export type ReviewAction =
  | "accept"
  | "edit"
  | "reject"
  | "mark_unknown";

export interface MetadataField {
  field_group: string;
  field_key: string;
  label: string;

  value: string;

  confidence: number;

  extraction_method: "label_value" | "regex" | "ai";

  evidence: SourceEvidence;

  verified: boolean;
  review_status: ReviewStatus;
  original_value: string;
}

export interface FieldAuditEntry {
  action: ReviewAction;
  previous_value: string | null;
  new_value: string | null;
  changed_by: string;
  changed_at: string;
}

export type RelationshipStatus =
  | "pending"
  | "confirmed"
  | "rejected"
  | "manual";

export interface DetectedRelationship {
  parent_document_id: string;
  parent_document_title: string;
  parent_document_number: string | null;

  relationship_type: string;

  confidence: number;

  matched_on: "contract_number" | "contract_title";

  status: RelationshipStatus;

  reasons: string[];
  detection_method: "automatic" | "manual";
}

export interface ChildRelationship {
  child_document_id: string;
  child_document_title: string;
  child_document_number: string | null;

  relationship_type: string;

  confidence: number;

  status: RelationshipStatus;

  reasons: string[];
}

export interface ChildRelationshipsResult {
  parent_document_id: string;
  children: ChildRelationship[];
}

export interface ApproveDocumentResult {
  document_id: string;
  approved_by: string;
  approved_at: string;
}

export interface PromoteDocumentResult {
  document_id: string;
  promoted_by: string;
  promoted_at: string;
}

export interface ContractAnalysisResult {
  document_id: string;

  classification: ContractClassification;

  metadata_fields: MetadataField[];

  relationship: DetectedRelationship | null;

  warnings: string[];
}

export type RelationshipAction = "confirm" | "reject";

export interface ConfirmRelationshipResult {
  document_id: string;
  status: "confirmed" | "rejected";
  relationship: DetectedRelationship | null;
}

export interface RenewalTerms {
  type: "automatic" | "manual" | null;
  period_months: number | null;
  notice_days: number | null;
}

export type StructuredContractOutput = Record<string, unknown> & {
  renewal?: RenewalTerms;
};

export interface HighlightBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface PageRender {
  page_number: number;
  image_data_url: string;
  page_width: number;
  page_height: number;
  highlight: HighlightBox | null;
}

export interface ClauseResult {
  clause_type: string;
  classification: string;
  extracted_text: string;
  value_summary: string;
  confidence: number;
  evidence: SourceEvidence;
}

export interface ClauseExtractionResult {
  document_id: string;
  clauses: ClauseResult[];
  warnings: string[];
}

export interface RateCardRow {
  role: string;
  rate: number | null;
  unit: string | null;
  currency: string | null;
}

export interface NormalizedTable {
  table_id: string;
  table_type: "rate_card" | "generic";
  page_number: number;
  source_reference: string;
  headers: string[];
  rows: Record<string, unknown>[];
  rate_card_rows: RateCardRow[];
}

export interface TableExtractionResult {
  document_id: string;
  tables: NormalizedTable[];
}

export interface SignatureResult {
  party_name: string;
  signatory_name: string;
  signatory_title: string;
  signed: boolean;
  signature_date: string | null;
  confidence: number;
  evidence: SourceEvidence;
}

export interface SignatureExtractionResult {
  document_id: string;
  signatures: SignatureResult[];
  warnings: string[];
}

export type ExtractionFieldDataType =
  | "text"
  | "number"
  | "currency"
  | "date"
  | "boolean"
  | "list";

export interface ExtractionField {
  id: number;
  model_id: number;
  field_name: string;
  description: string;
  data_type: ExtractionFieldDataType;
  created_at: string;
}

export interface ExtractionModel {
  id: number;
  name: string;
  description: string;
  created_at: string;
  fields: ExtractionField[];
}
