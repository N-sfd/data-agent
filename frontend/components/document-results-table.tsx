"use client";

import { useRouter } from "next/navigation";

import ConfidenceIndicator from "@/components/confidence-indicator";
import DocumentTypeBadge from "@/components/document-type-badge";
import EmptyState from "@/components/illustrations/empty-state";
import StatusBadge from "@/components/status-badge";
import { getDocumentTypeAppearance } from "@/lib/document-type-icon";
import { formatRelativeTime } from "@/lib/format";
import type { DocumentSummary } from "@/types/document";

function contractTitle(document: DocumentSummary): string {
  return document.original_filename.replace(/\.[^.]+$/, "");
}

interface DocumentResultsTableProps {
  documents: DocumentSummary[];
  emptyMessage: string;
  showExtendedColumns?: boolean;
  repositoryMode?: boolean;
  dashboardMode?: boolean;
}

export default function DocumentResultsTable({
  documents,
  emptyMessage,
  showExtendedColumns = false,
  repositoryMode = false,
  dashboardMode = false,
}: DocumentResultsTableProps) {
  const router = useRouter();

  if (documents.length === 0) {
    return (
      <EmptyState
        variant="documents"
        description={emptyMessage}
      />
    );
  }

  const fullRepository = repositoryMode && !dashboardMode;

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-border">
            <th className="px-8 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
              Contract
            </th>
            {fullRepository && (
              <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                Counterparty
              </th>
            )}
            <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
              Type
            </th>
            {fullRepository && (
              <>
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Effective
                </th>
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Expires
                </th>
                <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Value
                </th>
              </>
            )}
            <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
              Confidence
            </th>
            {(fullRepository || dashboardMode) && (
              <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                {fullRepository ? "Review" : "Status"}
              </th>
            )}
            {fullRepository && (
              <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                Relationship
              </th>
            )}
            {!dashboardMode && showExtendedColumns && !fullRepository && (
              <th className="px-4 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                Status
              </th>
            )}
            <th className="px-8 py-4 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
              Updated
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const appearance = getDocumentTypeAppearance(
              document.original_filename,
              document.document_type,
            );
            const TypeIcon = appearance.Icon;

            return (
            <tr
              key={document.document_id}
              onClick={() =>
                router.push(`/documents/${document.document_id}/review`)
              }
              className="cursor-pointer border-b border-border/60 transition duration-200 last:border-0 table-row-hover"
            >
              <td className="px-8 py-[18px]">
                <div className="flex items-start gap-3">
                  <span
                    className={[
                      "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border/70",
                      appearance.bgClass,
                    ].join(" ")}
                    title={appearance.label}
                  >
                    <TypeIcon
                      className={["h-4 w-4", appearance.iconClass].join(" ")}
                      strokeWidth={1.75}
                    />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[15px] font-medium text-foreground">
                      {document.document_type ?? contractTitle(document)}
                    </p>
                    <p className="mt-0.5 text-sm text-text-secondary">
                      {document.original_filename}
                    </p>
                  </div>
                </div>
              </td>
              {fullRepository && (
                <td className="px-5 py-[18px] text-sm text-text-secondary">
                  {document.counterparty ?? "—"}
                </td>
              )}
              <td className="px-4 py-5">
                <DocumentTypeBadge documentType={document.document_type} size="sm" />
              </td>
              {fullRepository && (
                <>
                  <td className="px-5 py-[18px] text-sm text-text-secondary">
                    {document.effective_date ?? "—"}
                  </td>
                  <td className="px-5 py-[18px] text-sm text-text-secondary">
                    {document.expiration_date ?? "—"}
                  </td>
                  <td className="px-5 py-[18px] text-sm text-text-secondary">
                    {document.contract_value ?? "—"}
                  </td>
                </>
              )}
              <td className="px-4 py-5">
                {document.confidence !== null ? (
                  <ConfidenceIndicator confidence={document.confidence} />
                ) : (
                  "—"
                )}
              </td>
              {fullRepository && (
                <td className="px-5 py-[18px]">
                  <StatusBadge
                    kind="repository"
                    status={document.repository_status ?? "not_approved"}
                  />
                </td>
              )}
              {dashboardMode && (
                <td className="px-5 py-[18px]">
                  <StatusBadge kind="document" status={document.status} />
                </td>
              )}
              {fullRepository && (
                <td className="px-5 py-[18px] text-sm text-text-secondary">
                  {document.relationship ?? "—"}
                </td>
              )}
              {!dashboardMode && showExtendedColumns && !fullRepository && (
                <td className="px-5 py-[18px]">
                  <StatusBadge kind="document" status={document.status} />
                </td>
              )}
              <td className="px-8 py-5 text-sm text-text-secondary">
                {formatRelativeTime(document.last_updated)}
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
