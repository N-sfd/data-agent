import type { DocumentTarget, TargetType } from "@/types/document";

/**
 * Family-aware suggested extraction groups.
 * Only groups that match at least one discovered target are shown.
 * Contract groups never appear for lab/financial docs (and vice versa).
 */

export interface SuggestionGroupDef {
  id: string;
  label: string;
  /** Prefer selecting this group by default when it has matches. */
  defaultSelected?: boolean;
  matchKeys?: string[];
  matchLabels?: RegExp[];
  matchTypes?: TargetType[];
}

const LAB_GROUPS: SuggestionGroupDef[] = [
  {
    id: "patient_report",
    label: "Patient / Report Information",
    defaultSelected: true,
    matchLabels: [
      /patient/i,
      /report\s*(info|information|date|id)/i,
      /specimen/i,
      /ordering/i,
      /physician/i,
      /dob|date of birth/i,
    ],
  },
  {
    id: "cbc",
    label: "Complete Blood Count",
    defaultSelected: true,
    matchKeys: ["complete_blood_count", "cbc"],
    matchLabels: [
      /complete blood count|\bcbc\b/i,
      /hemoglobin|\bhgb\b|\bwbc\b|\brbc\b|platelet|hematocrit/i,
    ],
  },
  {
    id: "iron_studies",
    label: "Iron Studies",
    defaultSelected: true,
    matchLabels: [/iron|ferritin|tibc|transferrin/i],
  },
  {
    id: "abnormal_results",
    label: "Abnormal Results",
    defaultSelected: true,
    matchLabels: [/abnormal|flagged|out of range|critical/i],
  },
  {
    id: "reference_ranges",
    label: "Reference Ranges",
    defaultSelected: true,
    matchLabels: [/reference\s*range|normal\s*range|ref\.?\s*range/i],
  },
  {
    id: "all_lab_results",
    label: "All Laboratory Results",
    defaultSelected: true,
    matchTypes: ["table"],
    matchLabels: [/lab|result|panel|assay|hematology|chemistry/i],
  },
];

const FINANCIAL_GROUPS: SuggestionGroupDef[] = [
  {
    id: "financial_summary",
    label: "Financial Summary",
    defaultSelected: true,
    matchKeys: ["financial_summary"],
    matchLabels: [/financial\s+summary/i],
  },
  {
    id: "revenue_analysis",
    label: "Revenue Analysis",
    defaultSelected: true,
    matchKeys: ["revenue_analysis", "revenue"],
    matchLabels: [/revenue/i],
  },
  {
    id: "operating_expenses",
    label: "Operating Expenses",
    defaultSelected: true,
    matchKeys: ["operating_expenses"],
    matchLabels: [/operating\s+expenses?/i],
  },
  {
    id: "budget_vs_actual",
    label: "Budget vs Actual",
    defaultSelected: true,
    matchKeys: ["budget_vs_actual"],
    matchLabels: [/budget\s+vs/i],
  },
  {
    id: "accounts_payable",
    label: "Accounts Payable",
    defaultSelected: true,
    matchKeys: ["accounts_payable"],
    matchLabels: [/accounts?\s+payable/i],
  },
  {
    id: "vendor_balances",
    label: "Vendor Balances",
    defaultSelected: true,
    matchKeys: ["vendor_balances"],
    matchLabels: [/vendor\s+balances?/i],
  },
  {
    id: "all_tables",
    label: "All Tables",
    defaultSelected: false,
    matchTypes: ["table"],
  },
];

const CONTRACT_GROUPS: SuggestionGroupDef[] = [
  {
    id: "contract_summary",
    label: "Contract Summary",
    defaultSelected: true,
    matchKeys: ["contract_number", "contract_no", "solicitation_number"],
    matchLabels: [
      /contract\s*(no|number|title|type)/i,
      /solicitation/i,
      /award\s*date/i,
    ],
  },
  {
    id: "parties",
    label: "Parties",
    defaultSelected: true,
    matchTypes: ["contact"],
    matchLabels: [
      /party|parties|contractor|vendor|supplier|customer|issued by|ship to/i,
    ],
  },
  {
    id: "dates",
    label: "Key Dates",
    defaultSelected: true,
    matchTypes: ["date"],
    matchLabels: [/effective|expiration|expiry|start date|end date|period of performance/i],
  },
  {
    id: "clauses",
    label: "Clauses",
    defaultSelected: true,
    matchTypes: ["clause"],
    matchLabels: [/clause|provision/i],
  },
  {
    id: "far_dfars",
    label: "FAR / DFARS",
    defaultSelected: true,
    matchKeys: ["far_clauses", "dfars_clauses"],
    matchLabels: [/\bfar\b|\bdfars\b/i],
  },
  {
    id: "supplier_agreement",
    label: "Supplier / Commercial Terms",
    defaultSelected: false,
    matchLabels: [/payment terms|governing law|liability|termination|warranty/i],
  },
  {
    id: "clins_pricing",
    label: "CLINs / Pricing",
    defaultSelected: true,
    matchKeys: ["clins", "pricing_table", "supplies_services"],
    matchLabels: [/\bclin\b|pricing|supplies.*services/i],
  },
];

const INVOICE_GROUPS: SuggestionGroupDef[] = [
  {
    id: "invoice_header",
    label: "Invoice Header",
    defaultSelected: true,
    matchKeys: ["invoice_number", "amount_due", "po_number"],
    matchLabels: [/invoice|bill to|remit|amount due|po number/i],
  },
  {
    id: "line_items",
    label: "Line Items",
    defaultSelected: true,
    matchTypes: ["table"],
    matchLabels: [/line item|description|quantity|unit price/i],
  },
];

const FAMILY_TO_GROUPS: Record<string, SuggestionGroupDef[]> = {
  laboratory_report: LAB_GROUPS,
  financial_report: FINANCIAL_GROUPS,
  financial_statement: FINANCIAL_GROUPS,
  budget: FINANCIAL_GROUPS,
  statement: FINANCIAL_GROUPS,
  invoice: INVOICE_GROUPS,
  purchase_order: INVOICE_GROUPS,
  government_contract: CONTRACT_GROUPS,
  contract: CONTRACT_GROUPS,
  master_services_agreement: CONTRACT_GROUPS,
  supplier_agreement: CONTRACT_GROUPS,
  sow: CONTRACT_GROUPS,
  amendment: CONTRACT_GROUPS,
  procurement: CONTRACT_GROUPS,
};

export interface ResolvedSuggestionGroup {
  id: string;
  label: string;
  targetIds: string[];
  defaultSelected: boolean;
}

function targetMatchesDef(
  target: DocumentTarget,
  def: SuggestionGroupDef,
): boolean {
  if (def.matchKeys?.some((key) => target.key === key || target.key.includes(key))) {
    return true;
  }
  if (def.matchTypes?.includes(target.target_type)) {
    // Type-only match still needs a label hint when labels are also defined,
    // except for explicit catch-alls like "All Tables".
    if (!def.matchLabels || def.matchLabels.length === 0) {
      return true;
    }
  }
  if (def.matchLabels?.some((pattern) => pattern.test(target.label))) {
    return true;
  }
  if (
    def.matchTypes?.includes(target.target_type) &&
    def.matchLabels?.some((pattern) => pattern.test(target.label))
  ) {
    return true;
  }
  // All-tables style: type match without requiring label
  if (
    def.matchTypes?.includes(target.target_type) &&
    (!def.matchLabels || def.matchLabels.length === 0) &&
    (!def.matchKeys || def.matchKeys.length === 0)
  ) {
    return true;
  }
  return false;
}

export function resolveSuggestionGroups(
  documentFamily: string | null | undefined,
  targets: DocumentTarget[],
): ResolvedSuggestionGroup[] {
  const defs = FAMILY_TO_GROUPS[documentFamily ?? ""] ?? [];
  if (defs.length === 0 || targets.length === 0) {
    return [];
  }

  const assigned = new Set<string>();
  const groups: ResolvedSuggestionGroup[] = [];

  for (const def of defs) {
    const matched = targets.filter((target) => {
      if (assigned.has(target.id) && def.id !== "all_tables" && def.id !== "all_lab_results") {
        // Allow overlap for catch-all groups only
      }
      return targetMatchesDef(target, def);
    });

    if (matched.length === 0) continue;

    const ids = matched.map((t) => t.id);
    for (const id of ids) {
      if (def.id !== "all_tables" && def.id !== "all_lab_results") {
        assigned.add(id);
      }
    }

    groups.push({
      id: def.id,
      label: def.label,
      targetIds: ids,
      defaultSelected: def.defaultSelected ?? false,
    });
  }

  return groups;
}

export function isContractFamily(family: string | null | undefined): boolean {
  if (!family) return false;
  return [
    "contract",
    "government_contract",
    "master_services_agreement",
    "supplier_agreement",
    "sow",
    "amendment",
    "procurement",
  ].includes(family);
}
