import FieldResult from "@/components/extraction/field-result";
import TableResult from "@/components/extraction/table-result";
import type {
  ExtractTargetsResult,
  ScalarTargetResult,
  TableTargetResult,
  UniversalTable,
  UniversalValue,
} from "@/types/document";

interface TargetResultsProps {
  result: ExtractTargetsResult;
}

function scalarToUniversalValue(scalar: ScalarTargetResult): UniversalValue {
  return {
    label: scalar.normalized_key,
    value: scalar.value,
    value_type: "text",
    confidence: scalar.confidence,
    extraction_method: scalar.extraction_method,
    evidence: scalar.evidence,
    verified: scalar.verified,
  };
}

function tableToUniversalTable(
  table: TableTargetResult,
  index: number,
): UniversalTable {
  return {
    table_id: `${table.target}-${index}`,
    title: table.target,
    headers: table.columns,
    rows: table.rows,
    page_number: table.pages[0] ?? 0,
    confidence: 1,
    source_reference: table.pages.length
      ? `pages ${table.pages.join(", ")}`
      : "",
  };
}

export default function TargetResults({ result }: TargetResultsProps) {
  const values = result.scalars.map(scalarToUniversalValue);
  const tables = result.tables.map(tableToUniversalTable);

  return (
    <div className="space-y-6">
      {result.unresolved_targets.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          {result.unresolved_targets.length} selected target
          {result.unresolved_targets.length === 1 ? "" : "s"} could not be
          resolved in this document.
        </div>
      )}

      {values.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Extracted data
          </h3>
          <div className="mt-4">
            <FieldResult values={values} />
          </div>
        </div>
      )}

      {tables.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-slate-900">
            Extracted tables
          </h3>
          <div className="space-y-4">
            {tables.map((table) => (
              <TableResult key={table.table_id} table={table} />
            ))}
          </div>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-500">
          {result.warnings.map((warning, index) => (
            <p key={index}>{warning}</p>
          ))}
        </div>
      )}
    </div>
  );
}
