import { apiFetch } from "@/lib/api";

/** Mirrors backend app/services/portfolio_insights.py. */

export interface NamedCount {
  name: string;
  count: number;
}

export type RiskSeverity = "high" | "medium" | "low";

export interface RiskItem {
  document_id: string;
  filename: string;
  kind: string;
  severity: RiskSeverity;
  detail: string;
}

export interface ExpiringPeriod {
  document_id: string;
  filename: string;
  contract_number: string | null;
  period: string;
  end_date: string;
  days_left: number;
}

export interface Portfolio {
  generated_at: string;
  totals: {
    documents: number;
    pages: number;
    ocr_pages: number;
    processed: number;
    processing: number;
    not_processed: number;
    failed: number;
    average_processing_seconds: number | null;
    staged: number;
  };
  document_mix: NamedCount[];
  uploads_by_month: { month: string; count: number }[];
  review: {
    fields: number;
    pending: number;
    accepted: number;
    edited: number;
    rejected: number;
    average_confidence: number | null;
    low_confidence_documents: number;
  };
  contracts: {
    count: number;
    agencies: NamedCount[];
    contractors: NamedCount[];
    vehicles: NamedCount[];
    naics: NamedCount[];
  };
  clauses: {
    references: number;
    top: { clause_number: string; title: string; documents: number }[];
  };
  expiring: ExpiringPeriod[];
  risks: {
    total: number;
    by_severity: Record<RiskSeverity, number>;
    by_kind: NamedCount[];
    items: RiskItem[];
  };
}

export function getPortfolio(): Promise<Portfolio> {
  return apiFetch<Portfolio>("/api/dashboard/portfolio");
}
