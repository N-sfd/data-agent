import { apiFetch } from "@/lib/api";
import type { CorrectionAction, TargetCorrection } from "@/types/document";

export interface SaveTargetCorrectionPayload {
  action?: CorrectionAction;
  originalValue: unknown;
  correctedValue?: unknown;
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
        action: payload.action ?? "edit",
        original_value: payload.originalValue,
        corrected_value: payload.correctedValue ?? null,
        evidence: payload.evidence ?? null,
        changed_by: payload.changedBy ?? null,
      }),
    },
  );
}

/** Records that a reviewer confirmed the current value is correct,
 * without changing it — a distinct action from editing. */
export async function markTargetVerified(
  documentId: string,
  normalizedKey: string,
  originalValue: unknown,
  evidence?: SaveTargetCorrectionPayload["evidence"],
  changedBy?: string,
): Promise<TargetCorrection> {
  return saveTargetCorrection(documentId, normalizedKey, {
    action: "verify",
    originalValue,
    evidence,
    changedBy,
  });
}

/** Reject an extracted value — keeps the value but marks review_status rejected. */
export async function rejectTargetValue(
  documentId: string,
  normalizedKey: string,
  originalValue: unknown,
  evidence?: SaveTargetCorrectionPayload["evidence"],
  changedBy?: string,
): Promise<TargetCorrection> {
  return saveTargetCorrection(documentId, normalizedKey, {
    action: "reject",
    originalValue,
    evidence,
    changedBy,
  });
}

export async function listTargetCorrections(
  documentId: string,
): Promise<TargetCorrection[]> {
  return apiFetch(`/api/documents/${documentId}/corrections`);
}
