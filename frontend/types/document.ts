export interface UploadedDocument {
  document_id: string;
  original_filename: string;
  status: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  page_count: number;
  encrypted: boolean;
  uploaded_at: string;
  message: string;
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
