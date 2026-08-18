import type { DocumentStatus } from "@/types/document";

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  completed: "Complete",
  review_required: "Review",
  processing: "Processing",
};

export const STATUS_STYLES: Record<DocumentStatus, string> = {
  completed: "bg-emerald-50 text-emerald-700",
  review_required: "bg-amber-50 text-amber-700",
  processing: "bg-slate-100 text-slate-600",
};
