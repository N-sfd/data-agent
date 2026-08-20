"use client";

import { useRouter } from "next/navigation";

import ConfidenceIndicator from "@/components/confidence-indicator";
import { STATUS_LABELS, STATUS_STYLES } from "@/lib/document-status";
import { formatRelativeTime } from "@/lib/format";
import type {
  DocumentSummary,
  RepositoryStatus,
} from "@/types/document";

const REPOSITORY_STATUS_LABELS: Record<RepositoryStatus, string> = {
  not_approved: "Needs review",
  approved: "Reviewed",
  repository: "In repository",
};

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
      <div className="px-8 py-16 text-center text-[15px] text-text-secondary">
        {emptyMessage}
      </div>
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
          {documents.map((document) => (
            <tr
              key={document.document_id}
              onClick={() =>
                router.push(`/documents/${document.document_id}/review`)
              }
              className="cursor-pointer border-b border-border/60 transition duration-200 last:border-0 table-row-hover"
            >
              <td className="px-8 py-[18px]">
                <p className="text-[15px] font-medium text-foreground">
                  {document.document_type ?? contractTitle(document)}
                </p>
                <p className="mt-0.5 text-sm text-text-secondary">
                  {document.original_filename}
                </p>
              </td>
              {fullRepository && (
                <td className="px-5 py-[18px] text-sm text-text-secondary">
                  {document.counterparty ?? "—"}
                </td>
              )}
              <td className="px-4 py-5 text-sm text-text-secondary">
                {document.document_type ?? "—"}
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
                <td className="px-5 py-[18px] text-sm text-text-secondary">
                  {
                    REPOSITORY_STATUS_LABELS[
                      document.repository_status ?? "not_approved"
                    ]
                  }
                </td>
              )}
              {dashboardMode && (
                <td className="px-5 py-[18px]">
                  <span
                    className={[
                      "rounded-full px-2.5 py-0.5 text-xs font-medium",
                      STATUS_STYLES[document.status],
                    ].join(" ")}
                  >
                    {STATUS_LABELS[document.status]}
                  </span>
                </td>
              )}
              {fullRepository && (
                <td className="px-5 py-[18px] text-sm text-text-secondary">
                  {document.relationship ?? "—"}
                </td>
              )}
              {!dashboardMode && showExtendedColumns && !fullRepository && (
                <td className="px-5 py-[18px]">
                  <span
                    className={[
                      "rounded-full px-2.5 py-0.5 text-xs font-medium",
                      STATUS_STYLES[document.status],
                    ].join(" ")}
                  >
                    {STATUS_LABELS[document.status]}
                  </span>
                </td>
              )}
              <td className="px-8 py-5 text-sm text-text-secondary">
                {formatRelativeTime(document.last_updated)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
