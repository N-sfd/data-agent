import type { DocumentStatus } from "@/types/document";

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  completed: "Ready",
  review_required: "Needs Review",
  processing: "Processing",
  failed: "Failed",
};

export const STATUS_STYLES: Record<DocumentStatus, string> = {
  completed: "bg-success/10 text-success",
  review_required: "bg-warning/10 text-warning",
  processing: "bg-surface-soft text-text-secondary",
  failed: "bg-danger/10 text-danger",
};
