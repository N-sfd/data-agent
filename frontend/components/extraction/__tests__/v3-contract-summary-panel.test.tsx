import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import V3ContractSummaryPanel from "@/components/extraction/v3-contract-summary-panel";
import type { V3ContractSummaryRow } from "@/lib/v3-export";

function summary(overrides: Partial<V3ContractSummaryRow> = {}): V3ContractSummaryRow {
  return {
    contract_number: "47QRCA25DSF07",
    solicitation_rfp: "47QRCA23R0001",
    contract_vehicle: "GSA OASIS+ MAC",
    agency_office: null,
    contractor: "CHUGACH BATTELLE APPLIED SOLUTIONS JV LLC",
    award_date: "04/15/2025",
    ceiling_max_aggregate: "No maximum dollar ceiling (unlimited task order value)",
    minimum_guarantee: "$2,500.00",
    base_period: "5 years",
    options: "1 option period(s) of 5 years",
    max_duration: "10 years",
    task_order_range: null,
    naics: null,
    size_standard: "$47.0",
    source_file: "Contract_47QRCA25DSF07 (2).pdf",
    source_page: 2,
    evidence: "Contract Number -> 47QRCA25DSF07",
    qa_status: "Needs Review",
    ...overrides,
  };
}

describe("V3ContractSummaryPanel", () => {
  it("groups fields under their section headings", () => {
    render(<V3ContractSummaryPanel summary={summary()} />);
    expect(screen.getByText("Contract Identification")).toBeInTheDocument();
    expect(screen.getByText("Financial")).toBeInTheDocument();
    expect(screen.getByText("Ceiling / Max Aggregate")).toBeInTheDocument();
    expect(
      screen.getByText("No maximum dollar ceiling (unlimited task order value)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Minimum Guarantee")).toBeInTheDocument();
    expect(screen.getByText("$2,500.00")).toBeInTheDocument();
  });

  it("shows 'Not found' for empty fields rather than fabricating a value", () => {
    render(<V3ContractSummaryPanel summary={summary()} />);
    const notFound = screen.getAllByText("Not found");
    // agency_office, task_order_range, naics are all null in the fixture.
    expect(notFound.length).toBe(3);
  });

  it("opens source verification when a populated value is clicked", () => {
    const onOpenSource = vi.fn();
    render(<V3ContractSummaryPanel summary={summary()} onOpenSource={onOpenSource} />);
    fireEvent.click(screen.getByText("47QRCA25DSF07"));
    expect(onOpenSource).toHaveBeenCalledWith(
      expect.objectContaining({
        pageNumber: 2,
        label: "Contract Number",
        value: "47QRCA25DSF07",
      }),
    );
  });

  it("does not render empty fields as clickable", () => {
    render(<V3ContractSummaryPanel summary={summary()} onOpenSource={vi.fn()} />);
    const notFoundEls = screen.getAllByText("Not found");
    for (const el of notFoundEls) {
      expect(el.closest("button")).toBeNull();
    }
  });
});
