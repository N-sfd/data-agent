import type { DocumentStatus, DocumentSummary } from "@/types/document";

export type OperationalStatus =
  | "ready"
  | "verified"
  | "review"
  | "failed"
  | "processing";

export interface DocumentPresentation {
  typeLabel: string;
  profileLabel: string;
  status: OperationalStatus;
  statusLabel: string;
}

/** Display type and profile from the filename and stored document type.
 * The staging profile is authoritative once a document is opened; this is
 * only the list-row hint so users do not see a contract-only repository. */
export function presentDocument(document: DocumentSummary): DocumentPresentation {
  const name = document.original_filename.toLowerCase();
  const stored = (document.document_type ?? "").toLowerCase();

  let typeLabel = document.document_type?.trim() || "Document";
  let profileLabel = "Generic";

  if (name.includes("part_52") || (name.endsWith(".html") && name.includes("far"))) {
    typeLabel = "FAR";
    profileLabel = "FAR Part 52";
  } else if (stored.includes("invoice") || name.includes("invoice")) {
    typeLabel = "Invoice";
    profileLabel = "Invoice";
  } else if (
    stored.includes("certificate") ||
    name.includes("certificate") ||
    name.includes("matric")
  ) {
    typeLabel = "Certificate";
    profileLabel = "Generic";
  } else if (
    stored.includes("government") ||
    stored.includes("contract") ||
    name.includes("contract")
  ) {
    typeLabel = "Contract";
    profileLabel = "Contract V3";
  }

  const status = operationalStatus(document);
  return {
    typeLabel,
    profileLabel,
    status,
    statusLabel: STATUS_LABEL[status],
  };
}

const STATUS_LABEL: Record<OperationalStatus, string> = {
  ready: "Ready",
  verified: "Verified",
  review: "Review",
  failed: "Failed",
  processing: "Processing",
};

export function operationalStatus(document: {
  status: DocumentStatus;
  repository_status?: string | null;
}): OperationalStatus {
  if (document.status === "failed") return "failed";
  if (document.status === "processing") return "processing";
  if (document.status === "review_required") return "review";
  if (document.repository_status === "approved") return "verified";
  return "ready";
}

export function statusMark(status: OperationalStatus): string {
  if (status === "review") return "!";
  if (status === "failed") return "×";
  if (status === "processing") return "●";
  return "✓";
}
