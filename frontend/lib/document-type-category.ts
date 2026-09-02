export type DocumentTypeCategory =
  | "contract"
  | "invoice"
  | "solicitation"
  | "lab_report"
  | "financial_report"
  | "general";

export const DOCUMENT_TYPE_CATEGORY_LABELS: Record<
  DocumentTypeCategory,
  string
> = {
  contract: "Contract",
  invoice: "Invoice",
  solicitation: "Solicitation",
  lab_report: "Lab Report",
  financial_report: "Financial Report",
  general: "General Document",
};

const CONTRACT_KEYWORDS = [
  "agreement",
  "contract",
  "nda",
  "lease",
  "statement of work",
  "amendment",
  "change order",
  "service level",
  "license",
  "subcontract",
];

const INVOICE_KEYWORDS = ["invoice", "purchase order", "billing", "receipt"];
const SOLICITATION_KEYWORDS = [
  "solicitation",
  "rfp",
  "rfq",
  "rfi",
  "bid",
  "proposal",
];
const LAB_REPORT_KEYWORDS = ["lab report", "laboratory", "test result", "assay"];
const FINANCIAL_REPORT_KEYWORDS = [
  "financial report",
  "financial statement",
  "balance sheet",
  "income statement",
  "budget",
  "rate card",
];

function matchesAny(value: string, keywords: string[]): boolean {
  return keywords.some((keyword) => value.includes(keyword));
}

/**
 * Buckets the backend's freeform document_type string into 6 display
 * categories. Today the backend only emits contract-subtype values, so
 * invoice/solicitation/lab_report will rarely if ever match against real
 * data — the mapping still degrades gracefully to "general" for unknown
 * or null values, and is forward-compatible if broader classification
 * ever lands.
 */
export function categorizeDocumentType(
  documentType: string | null | undefined,
): DocumentTypeCategory {
  if (!documentType || documentType.toLowerCase() === "other") {
    return "general";
  }

  const value = documentType.toLowerCase();

  if (matchesAny(value, FINANCIAL_REPORT_KEYWORDS)) return "financial_report";
  if (matchesAny(value, LAB_REPORT_KEYWORDS)) return "lab_report";
  if (matchesAny(value, SOLICITATION_KEYWORDS)) return "solicitation";
  if (matchesAny(value, INVOICE_KEYWORDS)) return "invoice";
  if (matchesAny(value, CONTRACT_KEYWORDS)) return "contract";

  return "general";
}
