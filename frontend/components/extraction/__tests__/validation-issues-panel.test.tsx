import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ValidationIssuesPanel from "@/components/extraction/validation-issues-panel";
import { buildFieldRows } from "@/components/extraction/field-row";
import type { ScalarTargetResult } from "@/types/document";

function scalar(overrides: Partial<ScalarTargetResult> = {}): ScalarTargetResult {
  return {
    target: "contract_number",
    normalized_key: "contract_number",
    value: "W912DR-26-C-0042",
    page: 1,
    confidence: 0.9,
    confidence_band: "high",
    verified: true,
    extraction_method: "source_evidence",
    display_method: "",
    evidence: {
      page_number: 1,
      source_text: "text",
      source_reference: "Page 1",
    },
    ...overrides,
  };
}

describe("ValidationIssuesPanel", () => {
  it("shows a clean state when every field extracted cleanly", () => {
    const rows = buildFieldRows([scalar()], [], new Map());
    render(<ValidationIssuesPanel rows={rows} />);
    expect(screen.getByText(/no validation issues/i)).toBeInTheDocument();
  });

  it("lists a warning for every non-extracted field", () => {
    const rows = buildFieldRows(
      [scalar({ verified: false })],
      [{ key: "missing", label: "Missing Field" }],
      new Map(),
    );
    render(<ValidationIssuesPanel rows={rows} />);
    expect(screen.getByText(/2 fields need attention/i)).toBeInTheDocument();
    expect(screen.getByText("Missing Field")).toBeInTheDocument();
  });

  it("calls onIssueClick with the row id when an issue is clicked", () => {
    const onIssueClick = vi.fn();
    const rows = buildFieldRows([scalar({ verified: false })], [], new Map());
    render(<ValidationIssuesPanel rows={rows} onIssueClick={onIssueClick} />);

    fireEvent.click(screen.getByText("contract_number"));

    expect(onIssueClick).toHaveBeenCalledWith("contract_number");
  });
});
