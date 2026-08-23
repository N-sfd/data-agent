import { apiFetch } from "@/lib/api";

import type {
  ExtractionField,
  ExtractionFieldDataType,
  ExtractionModel,
} from "@/types/document";

export async function listExtractionModels(): Promise<
  ExtractionModel[]
> {
  return apiFetch("/api/extraction-models");
}

export async function createExtractionModel(
  name: string,
  description: string,
): Promise<ExtractionModel> {
  return apiFetch("/api/extraction-models", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name, description }),
  });
}

export async function deleteExtractionModel(
  modelId: number,
): Promise<void> {
  await apiFetch(`/api/extraction-models/${modelId}`, {
    method: "DELETE",
  });
}

export async function addExtractionField(
  modelId: number,
  fieldName: string,
  description: string,
  dataType: ExtractionFieldDataType,
): Promise<ExtractionModel> {
  return apiFetch(`/api/extraction-models/${modelId}/fields`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      field_name: fieldName,
      description,
      data_type: dataType,
    }),
  });
}

export async function deleteExtractionField(
  modelId: number,
  fieldId: number,
): Promise<ExtractionModel> {
  return apiFetch(
    `/api/extraction-models/${modelId}/fields/${fieldId}`,
    {
      method: "DELETE",
    },
  );
}

export type { ExtractionField, ExtractionModel };
