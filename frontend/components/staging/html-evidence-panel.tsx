"use client";

import { useEffect, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import {
  getRegionContext,
  type RegionContext,
  type SourceLocator,
} from "@/lib/staging-workbook";

/** Source verification for HTML: shows the value's structural origin —
 * heading trail, the label/value pair or the table with the originating
 * cell marked, and the DOM path — from the extracted structure, never by
 * rendering the source page's own markup. */
export default function HtmlEvidencePanel({
  documentId,
  request,
}: {
  documentId: string;
  request: SourceViewRequest;
}) {
  const [loaded, setLoaded] = useState<{ regionId: string; context: RegionContext | null; error: string | null } | null>(null);
  const regionId = request.regionId ?? null;

  useEffect(() => {
    if (!regionId) return;
    let cancelled = false;
    getRegionContext(documentId, regionId)
      .then((context) => {
        if (!cancelled) setLoaded({ regionId, context, error: null });
      })
      .catch(() => {
        if (!cancelled) {
          setLoaded({
            regionId,
            context: null,
            error: "Unable to load the HTML source structure for this value.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, regionId]);

  const current = loaded && loaded.regionId === regionId ? loaded : null;
  const context = current?.context ?? null;
  const locator: SourceLocator | null | undefined =
    request.locator ??
    context?.field?.source_locator ??
    context?.region?.source_locator ??
    context?.table?.source_locator;

  return (
    <div className="space-y-4 p-4 text-sm">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-teal">
          HTML source
        </p>
        {locator?.section_path && locator.section_path.length > 0 ? (
          <nav
            aria-label="Section trail"
            className="mt-1 flex flex-wrap items-center gap-1 text-xs text-text-secondary"
          >
            {locator.section_path.map((section, index) => (
              <span key={`${section}-${index}`} className="flex items-center gap-1">
                {index > 0 && <span aria-hidden>›</span>}
                <span className="font-medium text-foreground">{section}</span>
              </span>
            ))}
          </nav>
        ) : (
          <p className="mt-1 text-xs text-text-muted">No enclosing heading</p>
        )}
      </div>

      {current?.error && <p className="text-danger">{current.error}</p>}
      {!regionId &&
        (request.evidenceText ? (
          // Values read straight from a DOM element (no structure region):
          // the element's own text is the evidence.
          <div className="rounded-lg border border-primary/30 bg-primary/[0.04] p-3">
            <p className="text-xs text-text-secondary">{request.label}</p>
            <p
              data-evidence-highlight
              className="mt-0.5 max-h-72 overflow-y-auto whitespace-pre-wrap rounded bg-warning/20 px-1 text-foreground"
            >
              {request.evidenceText}
            </p>
            {request.extractionMethod && (
              <p className="mt-2 text-[11px] text-text-muted">
                Found by: {request.extractionMethod.replace(/_/g, " ")}
              </p>
            )}
          </div>
        ) : (
          <p className="text-text-muted">No structural region was recorded for this value.</p>
        ))}
      {regionId && !current && <p className="text-text-muted">Loading source structure...</p>}

      {context?.field && (
        <div className="rounded-lg border border-primary/30 bg-primary/[0.04] p-3">
          <p className="text-xs text-text-secondary">{context.field.label_text}</p>
          <p
            data-evidence-highlight
            className="mt-0.5 whitespace-pre-wrap rounded bg-warning/20 px-1 font-medium text-foreground"
          >
            {context.field.raw_value}
          </p>
          <p className="mt-2 text-[11px] text-text-muted">
            Found by: {context.field.structural_relation.replace(/_/g, " ")}
          </p>
        </div>
      )}

      {context?.table && (
        <div className="max-h-[50vh] overflow-auto rounded-lg border border-border">
          <table className="w-full min-w-max divide-y divide-border text-xs">
            <thead className="bg-surface-soft">
              <tr>
                {context.table.headers.map((header, index) => (
                  <th key={index} className="px-2 py-1.5 text-left font-semibold text-text-secondary">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {context.table.rows.map((row, r) => (
                <tr key={r} className={r === context.row_index ? "bg-primary/[0.06]" : ""}>
                  {row.map((cell, c) => {
                    const target = r === context.row_index && c === context.column_index;
                    return (
                      <td
                        key={c}
                        data-evidence-highlight={target ? "" : undefined}
                        className={`px-2 py-1.5 ${
                          target
                            ? "bg-warning/25 font-semibold text-foreground ring-1 ring-warning"
                            : "text-foreground"
                        }`}
                      >
                        {cell.text}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {context?.region && !context.field && !context.table && (
        <p className="whitespace-pre-wrap rounded-lg border border-border bg-surface-soft p-3 text-foreground">
          {context.region.text}
        </p>
      )}

      {locator && (
        <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-text-muted">DOM path</dt>
          <dd className="break-all font-mono text-text-secondary">{locator.dom_path ?? "—"}</dd>
          {locator.element_id && (
            <>
              <dt className="text-text-muted">Element id</dt>
              <dd className="font-mono text-text-secondary">#{locator.element_id}</dd>
            </>
          )}
          {locator.table_index != null && (
            <>
              <dt className="text-text-muted">Table</dt>
              <dd className="text-text-secondary">
                {locator.table_index + 1}
                {locator.row_index != null && locator.row_index >= 0
                  ? `, row ${locator.row_index + 1}`
                  : ""}
                {locator.column_index != null ? `, column ${locator.column_index + 1}` : ""}
              </dd>
            </>
          )}
        </dl>
      )}
    </div>
  );
}
