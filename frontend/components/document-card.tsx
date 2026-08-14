import {
    CalendarDays,
    FileCheck2,
    FileText,
    Hash,
  } from "lucide-react";
  
  import { formatBytes, formatDate } from "@/lib/format";
  import type { UploadedDocument } from "@/types/document";
  
  interface DocumentCardProps {
    document: UploadedDocument;
  }
  
  export default function DocumentCard({
    document,
  }: DocumentCardProps) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-red-50">
            <FileText className="h-6 w-6 text-red-600" />
          </div>
  
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600">
              Ready
            </p>
  
            <h2 className="mt-1 truncate text-lg font-semibold text-slate-950">
              {document.original_filename}
            </h2>
  
            <p className="mt-1 text-sm text-slate-500">
              {document.page_count} pages ·{" "}
              {formatBytes(document.size_bytes)}
            </p>
          </div>
        </div>
  
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <Info
            icon={<FileCheck2 className="h-4 w-4" />}
            label="Type"
            value="PDF document"
          />
  
          <Info
            icon={<CalendarDays className="h-4 w-4" />}
            label="Uploaded"
            value={formatDate(document.uploaded_at)}
          />
  
          <Info
            icon={<Hash className="h-4 w-4" />}
            label="Document ID"
            value={document.document_id.slice(0, 12)}
          />
  
          <Info
            icon={<FileCheck2 className="h-4 w-4" />}
            label="Encryption"
            value={document.encrypted ? "Encrypted" : "None"}
          />
        </div>
      </div>
    );
  }
  
  function Info({
    icon,
    label,
    value,
  }: {
    icon: React.ReactNode;
    label: string;
    value: string;
  }) {
    return (
      <div className="rounded-xl bg-slate-50 p-3">
        <div className="flex items-center gap-2 text-slate-400">
          {icon}
          <span className="text-xs">{label}</span>
        </div>
  
        <p className="mt-1 truncate text-sm font-medium text-slate-800">
          {value}
        </p>
      </div>
    );
  }