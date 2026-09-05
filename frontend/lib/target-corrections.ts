import { apiFetch } from "@/lib/api";
import type { TargetCorrection } from "@/types/document";

export interface SaveTargetCorrectionPayload {
  originalValue: unknown;
  correctedValue: unknown;
  evidence?: {
    page_number: number;
    source_text: string;
    source_reference: string;
  } | null;
  changedBy?: string;
}

export async function saveTargetCorrection(
  documentId: string,
  normalizedKey: string,
  payload: SaveTargetCorrectionPayload,
): Promise<TargetCorrection> {
  return apiFetch(
    `/api/documents/${documentId}/targets/${encodeURIComponent(normalizedKey)}/corrections`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        original_value: payload.originalValue,
        corrected_value: payload.correctedValue,
        evidence: payload.evidence ?? null,
        changed_by: payload.changedBy ?? null,
      }),
    },
  );
}

export async function listTargetCorrections(
  documentId: string,
): Promise<TargetCorrection[]> {
  return apiFetch(`/api/documents/${documentId}/corrections`);
}
