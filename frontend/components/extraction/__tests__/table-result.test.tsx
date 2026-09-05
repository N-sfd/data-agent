import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TableResult from "@/components/extraction/table-result";
import type { UniversalTable } from "@/types/document";

function table(overrides: Partial<UniversalTable> = {}): UniversalTable {
  return {
    table_id: "t1",
    title: "Line Items",
    headers: ["Item", "Amount"],
    rows: [
      { Item: "Widget", Amount: "100" },
      { Item: "Gadget", Amount: "200" },
    ],
    page_number: 2,
    confidence: 1,
    source_reference: "pages 2",
    ...overrides,
  };
}

describe("TableResult", () => {
  it("renders a real HTML table with headers and rows, not a JSON blob", () => {
    render(<TableResult table={table()} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Item")).toBeInTheDocument();
    expect(screen.getByText("Widget")).toBeInTheDocument();
    expect(screen.getByText("200")).toBeInTheDocument();
  });

  it("shows the source page reference", () => {
    render(<TableResult table={table()} />);
    expect(screen.getByText(/Page 2/)).toBeInTheDocument();
  });

  it("fires onViewSource with the table's page when provided", () => {
    const onViewSource = vi.fn();
    render(<TableResult table={table()} onViewSource={onViewSource} />);
    fireEvent.click(screen.getByText("View Source"));
    expect(onViewSource).toHaveBeenCalledWith(
      expect.objectContaining({ pageNumber: 2 }),
    );
  });

  describe("export", () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;

    afterEach(() => {
      URL.createObjectURL = originalCreateObjectURL;
      URL.revokeObjectURL = originalRevokeObjectURL;
      vi.restoreAllMocks();
    });

    it("triggers a CSV download when Export CSV is clicked", () => {
      URL.createObjectURL = vi.fn(() => "blob:mock");
      URL.revokeObjectURL = vi.fn();
      const clickSpy = vi
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => {});

      render(<TableResult table={table()} />);
      fireEvent.click(screen.getByText("Export CSV"));

      expect(clickSpy).toHaveBeenCalledTimes(1);
    });

    it("triggers a JSON download when Export JSON is clicked", () => {
      URL.createObjectURL = vi.fn(() => "blob:mock");
      URL.revokeObjectURL = vi.fn();
      const clickSpy = vi
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => {});

      render(<TableResult table={table()} />);
      fireEvent.click(screen.getByText("Export JSON"));

      expect(clickSpy).toHaveBeenCalledTimes(1);
    });
  });
});
