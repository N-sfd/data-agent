import {
  categorizeDocumentType,
  DOCUMENT_TYPE_CATEGORY_LABELS,
  type DocumentTypeCategory,
} from "@/lib/document-type-category";

const CATEGORY_STYLES: Record<DocumentTypeCategory, string> = {
  contract: "bg-primary/10 text-primary",
  invoice: "bg-success/10 text-success",
  solicitation: "bg-accent/10 text-accent",
  lab_report: "bg-warning/10 text-warning",
  financial_report: "bg-success/10 text-success",
  general: "bg-surface-soft text-text-secondary",
};

interface DocumentTypeBadgeProps {
  documentType: string | null | undefined;
  size?: "sm" | "md";
}

export default function DocumentTypeBadge({
  documentType,
  size = "md",
}: DocumentTypeBadgeProps) {
  const category = categorizeDocumentType(documentType);
  const sizeClass =
    size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-0.5 text-xs";

  return (
    <span
      className={[
        "inline-flex items-center rounded-full font-medium",
        sizeClass,
        CATEGORY_STYLES[category],
      ].join(" ")}
      title={documentType ?? undefined}
    >
      {DOCUMENT_TYPE_CATEGORY_LABELS[category]}
    </span>
  );
}
