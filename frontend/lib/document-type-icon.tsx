import {
  File,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface DocumentTypeAppearance {
  Icon: LucideIcon;
  label: string;
  bgClass: string;
  iconClass: string;
}

function extensionFromFilename(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? filename.slice(dot + 1).toLowerCase() : "";
}

export function getDocumentTypeAppearance(
  filename: string,
  documentType?: string | null,
): DocumentTypeAppearance {
  const ext = extensionFromFilename(filename);
  const typeHint = (documentType ?? "").toLowerCase();

  if (ext === "pdf" || typeHint.includes("contract") || typeHint.includes("agreement")) {
    return {
      Icon: FileText,
      label: documentType ?? "PDF",
      bgClass: "bg-primary/10",
      iconClass: "text-primary",
    };
  }

  if (ext === "docx" || ext === "doc") {
    return {
      Icon: FileType2,
      label: documentType ?? "Word",
      bgClass: "bg-accent/10",
      iconClass: "text-accent",
    };
  }

  if (["png", "jpg", "jpeg", "webp", "tif", "tiff"].includes(ext)) {
    return {
      Icon: FileImage,
      label: documentType ?? "Image",
      bgClass: "bg-warning/10",
      iconClass: "text-warning",
    };
  }

  if (ext === "xlsx" || ext === "csv" || typeHint.includes("financial")) {
    return {
      Icon: FileSpreadsheet,
      label: documentType ?? "Spreadsheet",
      bgClass: "bg-success/10",
      iconClass: "text-success",
    };
  }

  return {
    Icon: File,
    label: documentType ?? "Document",
    bgClass: "bg-surface-soft",
    iconClass: "text-text-muted",
  };
}
