import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import FieldsTable from "@/components/extraction/fields-table";
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
      source_text: "Contract Number: W912DR-26-C-0042",
      source_reference: "Page 1",
    },
    ...overrides,
  };
}

describe("FieldsTable", () => {
  it("renders a single extracted field with its confidence band and method", () => {
    const rows = buildFieldRows([scalar()], [], new Map());
    render(<FieldsTable title="Fields" rows={rows} />);

    expect(screen.getByText("contract_number")).toBeInTheDocument();
    expect(screen.getByText("W912DR-26-C-0042")).toBeInTheDocument();
    expect(screen.getByText(/high · 90%/i)).toBeInTheDocument();
  });

  it("renders 100+ fields without dropping rows", () => {
    const scalars = Array.from({ length: 120 }, (_, i) =>
      scalar({ target: `field_${i}`, normalized_key: `field_${i}` }),
    );
    const rows = buildFieldRows(scalars, [], new Map());
    render(<FieldsTable title="Fields" rows={rows} />);

    expect(screen.getAllByText("Extracted")).toHaveLength(120);
  });

  it("distinguishes missing, empty, low-confidence, and unverified fields with visible pills", () => {
    const rows = buildFieldRows(
      [
        scalar({ target: "a", normalized_key: "a", value: "" }),
        scalar({
          target: "b",
          normalized_key: "b",
          confidence_band: "low",
          confidence: 0.4,
        }),
        scalar({ target: "c", normalized_key: "c", verified: false }),
      ],
      [{ key: "d", label: "Missing Field" }],
      new Map(),
    );
    render(<FieldsTable title="Fields" rows={rows} />);

    expect(screen.getByText("Empty")).toBeInTheDocument();
    expect(screen.getByText("Needs review")).toBeInTheDocument();
    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(screen.getByText("Not found")).toBeInTheDocument();
    expect(screen.getByText("Missing Field")).toBeInTheDocument();
  });

  it("maps extraction methods to their display labels", () => {
    const rows = buildFieldRows(
      [
        scalar({ target: "a", normalized_key: "a", extraction_method: "ai" }),
        scalar({
          target: "b",
          normalized_key: "b",
          extraction_method: "form_field",
        }),
      ],
      [],
      new Map(),
    );
    render(<FieldsTable title="Fields" rows={rows} />);

    expect(screen.getByText("AI Fallback")).toBeInTheDocument();
    expect(screen.getByText("PDF Form Field")).toBeInTheDocument();
  });

  it("prefers the backend-provided display_method (e.g. an OCR label) over the generic mapping", () => {
    const rows = buildFieldRows(
      [scalar({ display_method: "OCR (Tesseract)" })],
      [],
      new Map(),
    );
    render(<FieldsTable title="Fields" rows={rows} />);

    expect(screen.getByText("OCR (Tesseract)")).toBeInTheDocument();
  });

  it("fires onViewSource with the field's page and highlight text", () => {
    const onViewSource = vi.fn();
    const rows = buildFieldRows([scalar()], [], new Map());
    render(<FieldsTable title="Fields" rows={rows} onViewSource={onViewSource} />);

    fireEvent.click(screen.getByText("View Source"));

    expect(onViewSource).toHaveBeenCalledWith(
      expect.objectContaining({
        pageNumber: 1,
        label: "contract_number",
        value: "W912DR-26-C-0042",
      }),
    );
  });

  it("saves a correction through the edit workflow", async () => {
    const onSaveCorrection = vi.fn().mockResolvedValue(undefined);
    const rows = buildFieldRows([scalar()], [], new Map());
    render(<FieldsTable title="Fields" rows={rows} onSaveCorrection={onSaveCorrection} />);

    fireEvent.click(screen.getByText("Edit"));
    const input = screen.getByDisplayValue("W912DR-26-C-0042");
    fireEvent.change(input, { target: { value: "W912DR-26-C-0043" } });
    fireEvent.click(screen.getByText("Save"));

    expect(onSaveCorrection).toHaveBeenCalledWith(
      expect.objectContaining({ id: "contract_number" }),
      "W912DR-26-C-0043",
    );
  });
});
