import {
  getContractAnalysis,
  getExtractResults,
  searchDocuments,
} from "@/lib/documents";
import {
  EXPLORER_FIELDS,
  type FieldAggregation,
  type FieldMatchRow,
  type FieldValueBucket,
  type ExplorerFieldKey,
} from "@/lib/field-schema";

async function loadFieldsForDocument(documentId: string): Promise<
  Array<{
    field_key: string;
    value: string;
    confidence: number | null;
  }>
> {
  try {
    const analysis = await getContractAnalysis(documentId);
    return analysis.metadata_fields.map((field) => ({
      field_key: field.field_key,
      value: field.value ?? "",
      confidence: field.confidence,
    }));
  } catch {
    // Target-only extracts never ran contract analyze — use durable
    // extract-results so Explorer still sees Select All values.
    try {
      const extract = await getExtractResults(documentId);
      return extract.scalars.map((scalar) => ({
        field_key: scalar.normalized_key,
        value: String(scalar.value ?? ""),
        confidence: scalar.confidence,
      }));
    } catch {
      return [];
    }
  }
}

// Render's free-tier backend is a single worker process; firing
// Promise.all across up to 100 documents (each up to two heavy calls —
// contract-analysis, with an extract-results fallback) sends a burst of
// ~100-200 simultaneous requests and can crash the process under real
// repository sizes. Cap how many documents are in flight at once so the
// page takes a bit longer instead of taking the backend down.
const MAX_CONCURRENT_DOCUMENT_LOADS = 5;

async function mapWithConcurrencyLimit<T, R>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < items.length) {
      const current = nextIndex;
      nextIndex += 1;
      results[current] = await fn(items[current]);
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, worker),
  );

  return results;
}

function fieldMatchesKey(
  fieldKey: string,
  explorerKey: ExplorerFieldKey,
): boolean {
  if (fieldKey === explorerKey) return true;
  // Discovered KV keys are often kv_contract_number style.
  if (fieldKey === `kv_${explorerKey}`) return true;
  if (fieldKey.endsWith(`_${explorerKey}`)) return true;
  if (fieldKey.includes(explorerKey)) return true;
  return false;
}

export async function aggregateFieldAcrossRepository(
  fieldKey: ExplorerFieldKey,
): Promise<FieldAggregation> {
  const fieldMeta = EXPLORER_FIELDS.find((field) => field.key === fieldKey);
  const fieldLabel = fieldMeta?.label ?? fieldKey;

  const { documents } = await searchDocuments({ limit: 100 });

  const matches: FieldMatchRow[] = [];
  const bucketCounts = new Map<string, number>();

  await mapWithConcurrencyLimit(
    documents,
    MAX_CONCURRENT_DOCUMENT_LOADS,
    async (doc) => {
      const fields = await loadFieldsForDocument(doc.document_id);
      if (fields.length === 0) return;

      const field = fields.find((item) =>
        fieldMatchesKey(item.field_key, fieldKey),
      );
      if (!field?.value?.trim()) return;

      const titleField = fields.find(
        (item) =>
          fieldMatchesKey(item.field_key, "contract_title" as ExplorerFieldKey) ||
          item.field_key.includes("title"),
      );
      const counterpartyField = fields.find(
        (item) =>
          fieldMatchesKey(item.field_key, "counterparty" as ExplorerFieldKey) ||
          fieldMatchesKey(item.field_key, "supplier" as ExplorerFieldKey),
      );
      const effectiveField = fields.find((item) =>
        fieldMatchesKey(item.field_key, "effective_date" as ExplorerFieldKey),
      );
      const expirationField = fields.find((item) =>
        fieldMatchesKey(item.field_key, "expiration_date" as ExplorerFieldKey),
      );

      const normalized = field.value.trim();
      bucketCounts.set(normalized, (bucketCounts.get(normalized) ?? 0) + 1);

      matches.push({
        document_id: doc.document_id,
        contract_title:
          titleField?.value ??
          doc.original_filename.replace(/\.[^.]+$/, ""),
        counterparty: counterpartyField?.value ?? doc.counterparty ?? null,
        field_value: normalized,
        effective_date: effectiveField?.value ?? doc.effective_date ?? null,
        expiration_date:
          expirationField?.value ?? doc.expiration_date ?? null,
        confidence: field.confidence,
      });
    },
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
