import FieldResult from "@/components/extraction/field-result";
import TableResult from "@/components/extraction/table-result";
import SourceVerificationPanel, {
  type SourceViewRequest,
} from "@/components/source-verification-panel";
import type {
  DocumentTarget,
  ExtractTargetsResult,
  ScalarTargetResult,
  TableTargetResult,
  TargetType,
  UniversalTable,
  UniversalValue,
} from "@/types/document";

interface TargetResultsProps {
  result: ExtractTargetsResult;
  /** Schema targets used to classify scalar results (contacts vs fields). */
  targets?: DocumentTarget[];
  documentId?: string;
  pageCount?: number;
  sourceRequest?: SourceViewRequest | null;
  onViewSource?: (request: SourceViewRequest) => void;
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

function isClauseLike(name: string): boolean {
  const lower = name.toLowerCase();
  return (
    lower.includes("clause") ||
    lower.includes("far") ||
    lower.includes("dfars") ||
    lower.includes("section") ||
    lower.includes("article")
  );
}

function inferScalarKind(
  scalar: ScalarTargetResult,
  typeByLabel: Map<string, TargetType>,
): "contact" | "identifier" | "field" {
  const fromSchema =
    typeByLabel.get(scalar.target.toLowerCase()) ??
    typeByLabel.get(scalar.normalized_key.toLowerCase());

  if (fromSchema === "contact") return "contact";
  if (fromSchema === "identifier") return "identifier";

  const label = `${scalar.target} ${scalar.normalized_key}`.toLowerCase();
  if (
    /email|phone|contact|fax|address|name|signatory|officer|poc|point of contact/.test(
      label,
    )
  ) {
    return "contact";
  }
  if (
    /identifier|id\b|number|code|clin|cage|uei|duns|solicitation|contract no/.test(
      label,
    )
  ) {
    return "identifier";
  }
  return "field";
}

function dedupeClauseTables(tables: TableTargetResult[]): TableTargetResult[] {
  const seen = new Map<string, TableTargetResult>();

  for (const table of tables) {
    const fingerprint = [
      table.target.toLowerCase(),
      table.columns.join("|"),
      JSON.stringify(table.rows.slice(0, 3)),
    ].join("::");

    const existing = seen.get(fingerprint);
    if (!existing) {
      seen.set(fingerprint, table);
      continue;
    }

    const pages = Array.from(
      new Set([...existing.pages, ...table.pages]),
    ).sort((a, b) => a - b);
    seen.set(fingerprint, { ...existing, pages });
  }

  return Array.from(seen.values());
}

export default function TargetResults({
  result,
  targets = [],
  documentId,
  pageCount = 1,
  sourceRequest = null,
  onViewSource,
}: TargetResultsProps) {
  const typeByLabel = new Map<string, TargetType>();
  const labelByKey = new Map<string, string>();
  for (const target of targets) {
    typeByLabel.set(target.label.toLowerCase(), target.target_type);
    typeByLabel.set(target.key.toLowerCase(), target.target_type);
    labelByKey.set(target.key, target.label);
  }

  const contactScalars: ScalarTargetResult[] = [];
  const identifierScalars: ScalarTargetResult[] = [];
  const fieldScalars: ScalarTargetResult[] = [];

  for (const scalar of result.scalars) {
    const kind = inferScalarKind(scalar, typeByLabel);
    if (kind === "contact") contactScalars.push(scalar);
    else if (kind === "identifier") identifierScalars.push(scalar);
    else fieldScalars.push(scalar);
  }

  const dataTables = result.tables.filter(
    (table) => !isClauseLike(table.target),
  );
  const clauseTables = dedupeClauseTables(
    result.tables.filter((table) => isClauseLike(table.target)),
  );

  return (
    <div className="space-y-6">
      {documentId && onViewSource && (
        <SourceVerificationPanel
          documentId={documentId}
          pageCount={pageCount}
          request={sourceRequest}
        />
      )}

      {result.unresolved_targets.length > 0 && (
        <div className="rounded-xl border border-warning/25 bg-warning/5 p-4 text-sm text-warning">
          <p>
            {result.unresolved_targets.length} selected target
            {result.unresolved_targets.length === 1 ? "" : "s"} could not be
            resolved in this document.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {result.unresolved_targets.map((targetKey) => (
              <li key={targetKey}>
                {labelByKey.get(targetKey) ?? targetKey}
                {labelByKey.has(targetKey) && (
                  <span className="ml-1 text-xs text-warning/80">
                    ({targetKey})
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {fieldScalars.length > 0 && (
        <div className="editorial-card p-5 sm:p-6">
          <h3 className="text-sm font-semibold text-foreground">Fields</h3>
          <div className="mt-3">
            <FieldResult
              values={fieldScalars.map(scalarToUniversalValue)}
              density="compact"
              onViewSource={onViewSource}
            />
          </div>
        </div>
      )}

      {identifierScalars.length > 0 && (
        <div className="editorial-card p-5 sm:p-6">
          <h3 className="text-sm font-semibold text-foreground">
            Identifiers & codes
          </h3>
          <div className="mt-3">
            <FieldResult
              values={identifierScalars.map(scalarToUniversalValue)}
              density="compact"
              onViewSource={onViewSource}
            />
          </div>
        </div>
      )}

      {contactScalars.length > 0 && (
        <div className="editorial-card p-5 sm:p-6">
          <h3 className="text-sm font-semibold text-foreground">Contacts</h3>
          <ul className="mt-3 divide-y divide-border rounded-xl border border-border">
            {contactScalars.map((scalar, index) => (
              <li
                key={`${scalar.target}-${index}`}
                className="flex flex-wrap items-start justify-between gap-3 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    {scalar.normalized_key}
                  </p>
                  <p className="mt-0.5 text-sm font-medium text-foreground">
                    {String(scalar.value ?? "")}
                  </p>
                  <p className="mt-1 text-xs text-text-secondary">
                    {scalar.evidence.source_reference || `Page ${scalar.page}`}
                    {scalar.verified ? " · Source verified" : ""}
                  </p>
                </div>
                {scalar.verified ? (
                  <span className="inline-flex items-center rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-semibold text-success">
                    Verified
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-surface-soft px-2 py-0.5 text-[11px] font-semibold text-text-muted">
                    p.{scalar.page}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {dataTables.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-foreground">Tables</h3>
          <div className="space-y-4">
            {dataTables.map((table, index) => (
              <TableResult
                key={tableToUniversalTable(table, index).table_id}
                table={tableToUniversalTable(table, index)}
                onViewSource={
                  onViewSource
                    ? (req) =>
                        onViewSource({
                          ...req,
                          value: table.target,
                          verified: true,
                        })
                    : undefined
                }
              />
            ))}
          </div>
        </div>
      )}

      {clauseTables.length > 0 && (
        <div className="editorial-card p-5 sm:p-6">
          <h3 className="text-sm font-semibold text-foreground">
            Clauses & sections
          </h3>
          <div className="mt-3 space-y-2">
            {clauseTables.map((table, index) => {
              const pages = table.pages.length
                ? `Pages ${table.pages.join(", ")}`
                : "Source pending";
              const preview =
                table.rows[0] && table.columns[0]
                  ? String(table.rows[0][table.columns[0]] ?? "")
                  : "";

              return (
                <details
                  key={`${table.target}-${index}`}
                  className="group rounded-xl border border-border bg-surface-soft"
                >
                  <summary className="cursor-pointer list-none px-4 py-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-foreground">
                          {table.target}
                        </p>
                        <p className="mt-0.5 text-xs text-text-secondary">
                          {pages}
                          {table.rows.length > 0 &&
                            ` · ${table.rows.length} row${table.rows.length === 1 ? "" : "s"}`}
                        </p>
                        {preview && (
                          <p className="mt-2 line-clamp-2 text-sm leading-5 text-text-secondary">
                            {preview}
                          </p>
                        )}
                      </div>
                      <span className="inline-flex items-center rounded-full bg-success/10 px-2.5 py-1 text-[11px] font-semibold text-success">
                        Source verified
                      </span>
                    </div>
                  </summary>
                  <div className="border-t border-border p-3">
                    <TableResult
                      table={tableToUniversalTable(table, index + 1000)}
                    />
                  </div>
                </details>
              );
            })}
          </div>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="rounded-xl border border-border bg-surface-soft p-4 text-xs text-text-secondary">
          {result.warnings.map((warning, index) => (
            <p key={index}>{warning}</p>
          ))}
        </div>
      )}
    </div>
  );
}
