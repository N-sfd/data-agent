import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ExtractedDataPanel from "@/components/extraction/extracted-data-panel";
import type { MetadataField } from "@/types/document";

vi.mock("@/lib/documents", () => ({
  searchDocuments: vi.fn(() => Promise.resolve({ total: 0 })),
}));

const FIELD: MetadataField = {
  field_group: "Identification",
  field_key: "contract_number",
  label: "Contract Number",
  value: "FA300224C0008",
  confidence: 0.97,
  extraction_method: "native",
  evidence: { page_number: 1, source_text: "CONTRACT NO. FA300224C0008", source_reference: "p1" },
  verified: true,
  review_status: "pending",
  original_value: "FA300224C0008",
};

describe("ExtractedDataPanel field rows", () => {
  it("never nests a button inside another button", () => {
    const { container } = render(<ExtractedDataPanel fields={[FIELD]} />);
    expect(screen.getByText("FA300224C0008")).toBeTruthy();
    for (const button of container.querySelectorAll("button")) {
      expect(button.parentElement?.closest("button")).toBeNull();
    }
  });

  it("toggles details by click and keyboard; the value opens its own popover", () => {
    render(<ExtractedDataPanel fields={[FIELD]} />);
    const row = screen.getByRole("button", { name: /Contract Number/ });
    expect(row.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(row);
    expect(row.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(row, { key: "Enter" });
    expect(row.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(screen.getByRole("button", { name: "FA300224C0008" }));
    expect(row.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("Open in Field Explorer")).toBeTruthy();
  });
});
