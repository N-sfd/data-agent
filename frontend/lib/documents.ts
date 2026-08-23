import { apiFetch } from "@/lib/api";

import type {
  ApproveDocumentResult,
  ChildRelationshipsResult,
  ClassificationHistoryEntry,
  ClassificationUpdate,
  ClauseExtractionResult,
  ConfirmRelationshipResult,
  ContractAnalysisResult,
  ContractClassification,
  DashboardStats,
  DetectedRelationship,
  DocumentHierarchyResult,
  DocumentPage,
  DocumentSearchResponse,
  DocumentSummary,
  DuplicateResolution,
  ExtractionProgress,
  ExtractionSummary,
  FieldAuditEntry,
  FinancialAnalysisResult,
  GlobalAuditLogResponse,
  MetadataField,
  PageRender,
  PromoteDocumentResult,
  RelationshipAction,
  ReviewAction,
  ReviewQueueEntry,
  SignatureExtractionResult,
  StructureDetectionResult,
  StructuredContractOutput,
  TableExtractionResult,
  UniversalExtractionResult,
  UploadedDocument,
} from "@/types/document";

export async function listDocuments(
  limit = 10,
): Promise<DocumentSummary[]> {
  return apiFetch(`/api/documents?limit=${limit}`);
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return apiFetch("/api/dashboard/stats");
}

export interface DocumentSearchParams {
  q?: string;
  status?: string;
  documentType?: string;
  confidence_min?: number;
  confidence_max?: number;
  repositoryStatus?: string;
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
  if (params.confidence_min !== undefined) {
    query.set("confidence_min", String(params.confidence_min));
  }
  if (params.confidence_max !== undefined) {
    query.set("confidence_max", String(params.confidence_max));
  }
  if (params.repositoryStatus) {
    query.set("repository_status", params.repositoryStatus);
  }
  query.set("limit", String(params.limit ?? 25));
  query.set("offset", String(params.offset ?? 0));

  return apiFetch(`/api/documents/search?${query.toString()}`);
}

export async function getGlobalAuditLog(
  limit = 50,
  offset = 0,
): Promise<GlobalAuditLogResponse> {
  return apiFetch(
    `/api/documents/audit-log?limit=${limit}&offset=${offset}`,
  );
}

export async function getReviewQueue(): Promise<ReviewQueueEntry[]> {
  return apiFetch("/api/dashboard/review-queue");
}

export async function resolveDuplicate(
  documentId: string,
  action: DuplicateResolution,
  originalFilename?: string,
): Promise<UploadedDocument> {
  return apiFetch(`/api/documents/${documentId}/resolve-duplicate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action,
      original_filename: originalFilename ?? null,
    }),
  });
}

export async function extractDocumentPages(
  documentId: string,
  onRetry?: (attempt: number, total: number) => void,
): Promise<ExtractionSummary> {
  return apiFetch(
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
    onRetry,
  );
}

export async function getExtractionProgress(
  documentId: string,
): Promise<ExtractionProgress> {
  return apiFetch(`/api/documents/${documentId}/progress`);
}

export async function getDocumentPages(
  documentId: string,
): Promise<DocumentPage[]> {
  return apiFetch(`/api/documents/${documentId}/pages`);
}

export async function detectStructures(
  documentId: string,
  onRetry?: (attempt: number, total: number) => void,
): Promise<StructureDetectionResult> {
  return apiFetch(
    `/api/documents/${documentId}/detect-structures`,
    { method: "POST" },
    onRetry,
  );
}

export async function analyzeFinancialDocument(
  documentId: string,
  instruction: string,
): Promise<FinancialAnalysisResult> {
  return apiFetch(`/api/documents/${documentId}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      instruction,
      page_start: null,
      page_end: null,
    }),
  });
}

export async function analyzeContract(
  documentId: string,
  extractionModelId?: number | null,
  onRetry?: (attempt: number, total: number) => void,
): Promise<ContractAnalysisResult> {
  return apiFetch(
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
    onRetry,
  );
}

export async function confirmRelationship(
  documentId: string,
  action: RelationshipAction,
  changedBy: string,
): Promise<ConfirmRelationshipResult> {
  return apiFetch(`/api/documents/${documentId}/confirm-relationship`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action, changed_by: changedBy }),
  });
}

export async function assignRelationship(
  documentId: string,
  parentDocumentId: string,
  changedBy: string,
  relationshipType = "amendment_of",
): Promise<DetectedRelationship> {
  return apiFetch(`/api/documents/${documentId}/relationship`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      parent_document_id: parentDocumentId,
      relationship_type: relationshipType,
      changed_by: changedBy,
    }),
  });
}

export async function removeRelationship(
  documentId: string,
  changedBy: string,
): Promise<void> {
  await apiFetch(`/api/documents/${documentId}/relationship`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ changed_by: changedBy }),
  });
}

export async function updateClassification(
  documentId: string,
  update: ClassificationUpdate,
): Promise<ContractClassification> {
  return apiFetch(`/api/documents/${documentId}/classification`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(update),
  });
}

export async function getClassificationHistory(
  documentId: string,
): Promise<ClassificationHistoryEntry[]> {
  return apiFetch(`/api/documents/${documentId}/classification-history`);
}

export async function getDocumentHierarchy(): Promise<DocumentHierarchyResult> {
  return apiFetch("/api/documents/hierarchy");
}

export async function getChildRelationships(
  documentId: string,
): Promise<ChildRelationshipsResult> {
  return apiFetch(`/api/documents/${documentId}/child-relationships`);
}

export async function approveDocument(
  documentId: string,
  changedBy: string,
): Promise<ApproveDocumentResult> {
  return apiFetch(`/api/documents/${documentId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ changed_by: changedBy }),
  });
}

export async function promoteDocument(
  documentId: string,
  changedBy: string,
): Promise<PromoteDocumentResult> {
  return apiFetch(`/api/documents/${documentId}/promote`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ changed_by: changedBy }),
  });
}

export async function getStructuredOutput(
  documentId: string,
): Promise<StructuredContractOutput> {
  return apiFetch(`/api/documents/${documentId}/structured-output`);
}

export async function getDocument(
  documentId: string,
): Promise<UploadedDocument> {
  return apiFetch(`/api/documents/${documentId}`);
}

export async function getContractAnalysis(
  documentId: string,
): Promise<ContractAnalysisResult> {
  return apiFetch(`/api/documents/${documentId}/analyze-contract`);
}

export async function getPageRender(
  documentId: string,
  pageNumber: number,
  highlight?: string,
): Promise<PageRender> {
  const params = highlight
    ? `?${new URLSearchParams({ highlight })}`
    : "";

  return apiFetch(
    `/api/documents/${documentId}/pages/${pageNumber}/render${params}`,
  );
}

export async function reviewMetadataField(
  documentId: string,
  fieldKey: string,
  action: ReviewAction,
  changedBy: string,
  value?: string,
): Promise<MetadataField> {
  return apiFetch(
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
}

export async function acceptAllMetadataFields(
  documentId: string,
  changedBy: string,
): Promise<MetadataField[]> {
  return apiFetch(`/api/documents/${documentId}/metadata-fields/accept-all`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ changed_by: changedBy }),
  });
}

export async function getFieldAuditLog(
  documentId: string,
  fieldKey: string,
): Promise<FieldAuditEntry[]> {
  return apiFetch(
    `/api/documents/${documentId}/metadata-fields/${fieldKey}/audit-log`,
  );
}

export async function extractClauses(
  documentId: string,
): Promise<ClauseExtractionResult> {
  return apiFetch(`/api/documents/${documentId}/extract-clauses`, {
    method: "POST",
  });
}

export async function getClauses(
  documentId: string,
): Promise<ClauseExtractionResult> {
  return apiFetch(`/api/documents/${documentId}/extract-clauses`);
}

export async function extractTables(
  documentId: string,
): Promise<TableExtractionResult> {
  return apiFetch(`/api/documents/${documentId}/extract-tables`, {
    method: "POST",
  });
}

export async function extractSignatures(
  documentId: string,
): Promise<SignatureExtractionResult> {
  return apiFetch(`/api/documents/${documentId}/extract-signatures`, {
    method: "POST",
  });
}

export async function getSignatures(
  documentId: string,
): Promise<SignatureExtractionResult> {
  return apiFetch(`/api/documents/${documentId}/extract-signatures`);
}

export async function universalExtract(
  documentId: string,
  instruction: string,
  onRetry?: (attempt: number, total: number) => void,
): Promise<UniversalExtractionResult> {
  return apiFetch(
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
    onRetry,
  );
}
