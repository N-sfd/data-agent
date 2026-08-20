import type { DocumentStatus } from "@/types/document";

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  completed: "Complete",
  review_required: "Review",
  processing: "Processing",
};

export const STATUS_STYLES: Record<DocumentStatus, string> = {
  completed: "bg-success/10 text-success",
  review_required: "bg-warning/10 text-warning",
  processing: "bg-surface-soft text-text-secondary",
};
