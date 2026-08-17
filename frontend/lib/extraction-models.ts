import { apiUrl } from "@/lib/api";

import type {
  ExtractionField,
  ExtractionFieldDataType,
  ExtractionModel,
} from "@/types/document";

export async function listExtractionModels(): Promise<
  ExtractionModel[]
> {
  const response = await fetch(
    apiUrl("/api/extraction-models"),
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to retrieve extraction models.",
    );
  }

  return result;
}

export async function createExtractionModel(
  name: string,
  description: string,
): Promise<ExtractionModel> {
  const response = await fetch(
    apiUrl("/api/extraction-models"),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name, description }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to create the extraction model.",
    );
  }

  return result;
}

export async function deleteExtractionModel(
  modelId: number,
): Promise<void> {
  const response = await fetch(
    apiUrl(`/api/extraction-models/${modelId}`),
    {
      method: "DELETE",
    },
  );

  if (!response.ok) {
    const result = await response.json().catch(() => null);

    throw new Error(
      typeof result?.detail === "string"
        ? result.detail
        : "Unable to delete the extraction model.",
    );
  }
}

export async function addExtractionField(
  modelId: number,
  fieldName: string,
  description: string,
  dataType: ExtractionFieldDataType,
): Promise<ExtractionModel> {
  const response = await fetch(
    apiUrl(`/api/extraction-models/${modelId}/fields`),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        field_name: fieldName,
        description,
        data_type: dataType,
      }),
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to add the field.",
    );
  }

  return result;
}

export async function deleteExtractionField(
  modelId: number,
  fieldId: number,
): Promise<ExtractionModel> {
  const response = await fetch(
    apiUrl(
      `/api/extraction-models/${modelId}/fields/${fieldId}`,
    ),
    {
      method: "DELETE",
    },
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Unable to delete the field.",
    );
  }

  return result;
}

export type { ExtractionField, ExtractionModel };
