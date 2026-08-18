import Link from "next/link";

import { STATUS_LABELS, STATUS_STYLES } from "@/lib/document-status";
import type { DocumentSummary } from "@/types/document";

interface DocumentResultsTableProps {
  documents: DocumentSummary[];
  emptyMessage: string;
}

export default function DocumentResultsTable({
  documents,
  emptyMessage,
}: DocumentResultsTableProps) {
  if (documents.length === 0) {
    return (
      <div className="p-10 text-center text-sm text-slate-500">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-3 text-left font-semibold text-slate-700">
              Contract
            </th>
            <th className="px-6 py-3 text-left font-semibold text-slate-700">
              Type
            </th>
            <th className="px-6 py-3 text-left font-semibold text-slate-700">
              Pages
            </th>
            <th className="px-6 py-3 text-left font-semibold text-slate-700">
              Extracted Fields
            </th>
            <th className="px-6 py-3 text-left font-semibold text-slate-700">
              Confidence
            </th>
            <th className="px-6 py-3 text-left font-semibold text-slate-700">
              Status
            </th>
            <th className="px-6 py-3 text-left font-semibold text-slate-700">
              Last Updated
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr
              key={document.document_id}
              className="border-t border-slate-100 hover:bg-slate-50"
            >
              <td className="px-6 py-3">
                <Link
                  href={`/documents/${document.document_id}/review`}
                  className="font-medium text-blue-700 hover:text-blue-800"
                >
                  {document.original_filename}
                </Link>
              </td>
              <td className="px-6 py-3 text-slate-600">
                {document.document_type ?? "—"}
              </td>
              <td className="px-6 py-3 text-slate-600">
                {document.page_count}
              </td>
              <td className="px-6 py-3 text-slate-600">
                {document.fields_extracted}
              </td>
              <td className="px-6 py-3 text-slate-600">
                {document.confidence !== null
                  ? `${Math.round(document.confidence * 100)}%`
                  : "—"}
              </td>
              <td className="px-6 py-3">
                <span
                  className={[
                    "rounded-full px-2.5 py-0.5 text-xs font-semibold",
                    STATUS_STYLES[document.status],
                  ].join(" ")}
                >
                  {STATUS_LABELS[document.status]}
                </span>
              </td>
              <td className="px-6 py-3 text-slate-500">
                {new Date(document.last_updated).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
