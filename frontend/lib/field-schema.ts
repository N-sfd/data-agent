export const EXPLORER_FIELDS = [
  { key: "payment_terms", label: "Payment Terms", group: "Financial" },
  { key: "currency", label: "Currency", group: "Financial" },
  { key: "contract_value", label: "Total / Contract Value", group: "Financial" },
  { key: "invoice_number", label: "Invoice Number", group: "Financial" },
  { key: "total_amount", label: "Total Amount", group: "Financial" },
  { key: "governing_law", label: "Governing Law", group: "Legal" },
  { key: "termination_rights", label: "Termination Rights", group: "Legal" },
  { key: "liability_cap", label: "Liability Cap", group: "Legal" },
  { key: "effective_date", label: "Effective Date", group: "Dates" },
  { key: "expiration_date", label: "Expiration Date", group: "Dates" },
  { key: "renewal_date", label: "Renewal Date", group: "Dates" },
  { key: "report_date", label: "Report Date", group: "Dates" },
  { key: "supplier", label: "Supplier", group: "Parties" },
  { key: "customer", label: "Customer", group: "Parties" },
  { key: "counterparty", label: "Counterparty", group: "Parties" },
  { key: "contract_type", label: "Document Type", group: "Identification" },
  { key: "contract_number", label: "Document / Contract Number", group: "Identification" },
  { key: "contract_title", label: "Document Title", group: "Identification" },
  { key: "sample_id", label: "Sample ID", group: "Lab / Scientific" },
  { key: "test_method", label: "Test Method", group: "Lab / Scientific" },
  { key: "result_value", label: "Result Value", group: "Lab / Scientific" },
  { key: "requirement_id", label: "Requirement ID", group: "BRD / Specs" },
  { key: "priority", label: "Priority", group: "BRD / Specs" },
] as const;

export type ExplorerFieldKey = (typeof EXPLORER_FIELDS)[number]["key"];

export interface FieldMatchRow {
  document_id: string;
  contract_title: string;
  counterparty: string | null;
  field_value: string;
  effective_date: string | null;
  expiration_date: string | null;
  confidence: number | null;
}

export interface FieldValueBucket {
  value: string;
  count: number;
}

export interface FieldAggregation {
  field_key: string;
  field_label: string;
  total_analyzed: number;
  buckets: FieldValueBucket[];
  matches: FieldMatchRow[];
}
