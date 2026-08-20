export const EXPLORER_FIELDS = [
  { key: "payment_terms", label: "Payment Terms", group: "Financial" },
  { key: "governing_law", label: "Governing Law", group: "Legal" },
  { key: "contract_value", label: "Contract Value", group: "Financial" },
  { key: "effective_date", label: "Effective Date", group: "Dates" },
  { key: "expiration_date", label: "Expiration Date", group: "Dates" },
  { key: "supplier", label: "Supplier", group: "Parties" },
  { key: "customer", label: "Customer", group: "Parties" },
  { key: "counterparty", label: "Counterparty", group: "Parties" },
  { key: "contract_type", label: "Contract Type", group: "Identification" },
  { key: "contract_number", label: "Contract Number", group: "Identification" },
  { key: "contract_title", label: "Contract Title", group: "Identification" },
  { key: "renewal_date", label: "Renewal Date", group: "Dates" },
  { key: "termination_rights", label: "Termination Rights", group: "Legal" },
  { key: "liability_cap", label: "Liability Cap", group: "Legal" },
  { key: "currency", label: "Currency", group: "Financial" },
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
