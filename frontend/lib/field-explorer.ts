import { getContractAnalysis, searchDocuments } from "@/lib/documents";
import {
  EXPLORER_FIELDS,
  type FieldAggregation,
  type FieldMatchRow,
  type FieldValueBucket,
  type ExplorerFieldKey,
} from "@/lib/field-schema";

export async function aggregateFieldAcrossRepository(
  fieldKey: ExplorerFieldKey,
): Promise<FieldAggregation> {
  const fieldMeta = EXPLORER_FIELDS.find((field) => field.key === fieldKey);
  const fieldLabel = fieldMeta?.label ?? fieldKey;

  const { documents } = await searchDocuments({ limit: 100 });

  const matches: FieldMatchRow[] = [];
  const bucketCounts = new Map<string, number>();

  await Promise.all(
    documents.map(async (doc) => {
      try {
        const analysis = await getContractAnalysis(doc.document_id);
        const field = analysis.metadata_fields.find(
          (item) => item.field_key === fieldKey,
        );

        if (!field?.value?.trim()) return;

        const titleField = analysis.metadata_fields.find(
          (item) => item.field_key === "contract_title",
        );
        const counterpartyField = analysis.metadata_fields.find(
          (item) =>
            item.field_key === "counterparty" ||
            item.field_key === "supplier",
        );
        const effectiveField = analysis.metadata_fields.find(
          (item) => item.field_key === "effective_date",
        );
        const expirationField = analysis.metadata_fields.find(
          (item) => item.field_key === "expiration_date",
        );

        const normalized = field.value.trim();
        bucketCounts.set(
          normalized,
          (bucketCounts.get(normalized) ?? 0) + 1,
        );

        matches.push({
          document_id: doc.document_id,
          contract_title:
            titleField?.value ??
            doc.original_filename.replace(/\.[^.]+$/, ""),
          counterparty:
            counterpartyField?.value ?? doc.counterparty ?? null,
          field_value: normalized,
          effective_date:
            effectiveField?.value ?? doc.effective_date ?? null,
          expiration_date:
            expirationField?.value ?? doc.expiration_date ?? null,
          confidence: field.confidence,
        });
      } catch {
        // Skip documents without analysis.
      }
    }),
  );

  const buckets: FieldValueBucket[] = [...bucketCounts.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count);

  return {
    field_key: fieldKey,
    field_label: fieldLabel,
    total_analyzed: documents.length,
    buckets,
    matches,
  };
}

export function filterMatchesByValue(
  aggregation: FieldAggregation,
  value: string,
): FieldMatchRow[] {
  return aggregation.matches.filter((row) => row.field_value === value);
}
