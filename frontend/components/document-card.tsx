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

export default function DocumentCard({ document }: DocumentCardProps) {
  return (
    <div className="editorial-card p-8">
      <div className="flex items-start gap-4">
        <div className="file-icon-wrap h-12 w-12 shrink-0">
          <FileText className="h-6 w-6" strokeWidth={1.75} />
        </div>

        <div className="min-w-0">
          <span className="inline-flex rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success">
            Upload complete
          </span>

          <h2 className="mt-2 truncate text-lg font-medium text-foreground">
            {document.original_filename}
          </h2>

          <p className="mt-1 text-sm text-text-secondary">
            {document.page_count} pages · {formatBytes(document.size_bytes)}
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <Info
          icon={<FileCheck2 className="h-4 w-4" strokeWidth={1.75} />}
          label="Type"
          value="PDF document"
        />

        <Info
          icon={<CalendarDays className="h-4 w-4" strokeWidth={1.75} />}
          label="Uploaded"
          value={formatDate(document.uploaded_at)}
        />

        <Info
          icon={<Hash className="h-4 w-4" strokeWidth={1.75} />}
          label="Document ID"
          value={document.document_id.slice(0, 12)}
        />

        <Info
          icon={<FileCheck2 className="h-4 w-4" strokeWidth={1.75} />}
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
    <div className="rounded-xl bg-surface-soft p-3.5">
      <div className="flex items-center gap-2 text-text-muted">
        {icon}
        <span className="text-xs">{label}</span>
      </div>

      <p className="mt-1 truncate text-sm font-medium text-foreground">
        {value}
      </p>
    </div>
  );
}
