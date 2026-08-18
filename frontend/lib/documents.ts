import { apiFetch } from "@/lib/api";

import type {
  ApproveDocumentResult,
  ChildRelationshipsResult,
  ClauseExtractionResult,
  ConfirmRelationshipResult,
  ContractAnalysisResult,
  DashboardStats,
  DocumentPage,
  DocumentSearchResponse,
  DocumentSummary,
  DuplicateResolution,
  ExtractionSummary,
  FieldAuditEntry,
  FinancialAnalysisResult,
  GlobalAuditLogResponse,
  MetadataField,
  PageRender,
  RelationshipAction,
  ReviewAction,
  ReviewQueueEntry,
  SignatureExtractionResult,
  StructuredContractOutput,
  TableExtractionResult,
  UniversalExtractionResult,
  UploadedDocument,
} from "@/types/document";

export async function listDocuments(
  limit = 10,
): Promise<DocumentSummary[]> {
  const response = await apiFetch(
    `/api/documents?limit=${limit}`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve documents.",
    );
  }

  return result;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await apiFetch("/api/dashboard/stats");

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve dashboard stats.",
    );
  }

  return result;
}

export interface DocumentSearchParams {
  q?: string;
  status?: string;
  documentType?: string;
  limit?: number;
  offset?: number;
}

export async function searchDocuments(
  params: DocumentSearchParams = {},
): Promise<DocumentSearchResponse> {
  const query = new URLSearchParams();

  if (params.q) query.set("q", params.q);
  if (params.status) query.set("status", params.status);
  if (params.documentType) {
    query.set("document_type", params.documentType);
  }
  query.set("limit", String(params.limit ?? 25));
  query.set("offset", String(params.offset ?? 0));

  const response = await apiFetch(
    `/api/documents/search?${query.toString()}`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to search documents.",
    );
  }

  return result;
}

export async function getGlobalAuditLog(
  limit = 50,
  offset = 0,
): Promise<GlobalAuditLogResponse> {
  const response = await apiFetch(
    `/api/documents/audit-log?limit=${limit}&offset=${offset}`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve the audit log.",
    );
  }

  return result;
}

export async function getReviewQueue(): Promise<ReviewQueueEntry[]> {
  const response = await apiFetch("/api/dashboard/review-queue");

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve the review queue.",
    );
  }

  return result;
}

export async function resolveDuplicate(
  documentId: string,
  action: DuplicateResolution,
  originalFilename?: string,
): Promise<UploadedDocument> {
  const response = await apiFetch(
    `/api/documents/${documentId}/resolve-duplicate`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        action,
        original_filename: originalFilename ?? null,
      }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to resolve the duplicate upload.",
    );
  }

  return result;
}

export async function extractDocumentPages(
  documentId: string,
): Promise<ExtractionSummary> {
  const response = await apiFetch(
    `/api/documents/${documentId}/extract-pages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        run_ocr: true,
        page_start: null,
        page_end: null,
        force_reprocess: false,
      }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Page extraction failed.",
    );
  }

  return result;
}

export async function getDocumentPages(
  documentId: string,
): Promise<DocumentPage[]> {
  const response = await apiFetch(
    `/api/documents/${documentId}/pages`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve extracted pages.",
    );
  }

  return result;
}

export async function analyzeFinancialDocument(
  documentId: string,
  instruction: string,
): Promise<FinancialAnalysisResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/analyze`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        instruction,
        page_start: null,
        page_end: null,
      }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Financial analysis failed.",
    );
  }

  return result;
}

export async function analyzeContract(
  documentId: string,
  extractionModelId?: number | null,
): Promise<ContractAnalysisResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/analyze-contract`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        extraction_model_id: extractionModelId ?? null,
      }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Contract analysis failed.",
    );
  }

  return result;
}

export async function confirmRelationship(
  documentId: string,
  action: RelationshipAction,
): Promise<ConfirmRelationshipResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/confirm-relationship`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ action }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to resolve the relationship.",
    );
  }

  return result;
}

export async function getChildRelationships(
  documentId: string,
): Promise<ChildRelationshipsResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/child-relationships`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve contract relationships.",
    );
  }

  return result;
}

export async function approveDocument(
  documentId: string,
  changedBy: string,
): Promise<ApproveDocumentResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/approve`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ changed_by: changedBy }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to approve this document.",
    );
  }

  return result;
}

export async function getStructuredOutput(
  documentId: string,
): Promise<StructuredContractOutput> {
  const response = await apiFetch(
    `/api/documents/${documentId}/structured-output`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve structured output.",
    );
  }

  return result;
}

export async function getDocument(
  documentId: string,
): Promise<UploadedDocument> {
  const response = await apiFetch(`/api/documents/${documentId}`);

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve the document.",
    );
  }

  return result;
}

export async function getContractAnalysis(
  documentId: string,
): Promise<ContractAnalysisResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/analyze-contract`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve the contract analysis.",
    );
  }

  return result;
}

export async function getPageRender(
  documentId: string,
  pageNumber: number,
  highlight?: string,
): Promise<PageRender> {
  const params = highlight
    ? `?${new URLSearchParams({ highlight })}`
    : "";

  const response = await apiFetch(
    `/api/documents/${documentId}/pages/${pageNumber}/render${params}`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to render the page.",
    );
  }

  return result;
}

export async function reviewMetadataField(
  documentId: string,
  fieldKey: string,
  action: ReviewAction,
  changedBy: string,
  value?: string,
): Promise<MetadataField> {
  const response = await apiFetch(
    `/api/documents/${documentId}/metadata-fields/${fieldKey}/review`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        action,
        value: value ?? null,
        changed_by: changedBy,
      }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to review the field.",
    );
  }

  return result;
}

export async function acceptAllMetadataFields(
  documentId: string,
  changedBy: string,
): Promise<MetadataField[]> {
  const response = await apiFetch(
    `/api/documents/${documentId}/metadata-fields/accept-all`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ changed_by: changedBy }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to accept all fields.",
    );
  }

  return result;
}

export async function getFieldAuditLog(
  documentId: string,
  fieldKey: string,
): Promise<FieldAuditEntry[]> {
  const response = await apiFetch(
    `/api/documents/${documentId}/metadata-fields/${fieldKey}/audit-log`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve the audit log.",
    );
  }

  return result;
}

export async function extractClauses(
  documentId: string,
): Promise<ClauseExtractionResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/extract-clauses`,
    {
      method: "POST",
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Clause extraction failed.",
    );
  }

  return result;
}

export async function getClauses(
  documentId: string,
): Promise<ClauseExtractionResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/extract-clauses`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve clauses.",
    );
  }

  return result;
}

export async function extractTables(
  documentId: string,
): Promise<TableExtractionResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/extract-tables`,
    {
      method: "POST",
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Table extraction failed.",
    );
  }

  return result;
}

export async function extractSignatures(
  documentId: string,
): Promise<SignatureExtractionResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/extract-signatures`,
    {
      method: "POST",
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Signature extraction failed.",
    );
  }

  return result;
}

export async function getSignatures(
  documentId: string,
): Promise<SignatureExtractionResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/extract-signatures`,
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve signatures.",
    );
  }

  return result;
}

export async function universalExtract(
  documentId: string,
  instruction: string,
): Promise<UniversalExtractionResult> {
  const response = await apiFetch(
    `/api/documents/${documentId}/extract`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        instruction,
        page_start: null,
        page_end: null,
        max_pages: 20,
        use_ai_fallback: true,
      }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : result.detail?.message ?? "Extraction failed.",
    );
  }

  return result;
}
