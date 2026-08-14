import { apiUrl } from "@/lib/api";

import type {
  DocumentPage,
  ExtractionSummary,
  FinancialAnalysisResult,
  UniversalExtractionResult,
} from "@/types/document";

export async function extractDocumentPages(
  documentId: string,
): Promise<ExtractionSummary> {
  const response = await fetch(
    apiUrl(
      `/api/documents/${documentId}/extract-pages`,
    ),
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
  const response = await fetch(
    apiUrl(`/api/documents/${documentId}/pages`),
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

  const response = await fetch(
    apiUrl(
      `/api/documents/${documentId}/analyze`,
    ),
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
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

export async function universalExtract(
  documentId: string,
  instruction: string,
): Promise<UniversalExtractionResult> {

  const response = await fetch(
    apiUrl(
      `/api/documents/${documentId}/extract`,
    ),
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
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

  const result =
    await response.json();

  if (!response.ok) {

    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : result.detail?.message
          ?? "Extraction failed.",
    );
  }

  return result;
}
