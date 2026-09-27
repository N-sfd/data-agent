import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HtmlEvidencePanel from "@/components/staging/html-evidence-panel";
import { canOpenSource, cellSourceRequest, locationLabel } from "@/components/staging/review-status";
import { getRegionContext, type StagingCell } from "@/lib/staging-workbook";

vi.mock("@/lib/staging-workbook", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/staging-workbook")>()),
  getRegionContext: vi.fn(),
}));

const getContext = vi.mocked(getRegionContext);

const locator = {
  dom_path: "/html/body/table/tbody/tr[2]/td[3]",
  element_id: null,
  section_path: ["Shipment Manifest"],
  table_index: 0,
  row_index: 1,
  column_index: 2,
  sheet_name: null,
  cell_ref: null,
};

function htmlCell(): StagingCell {
  return {
    canonical_field: "document.line_item.description",
    display_label: "Description",
    value: "Quick coupler, brass",
    raw_value: "Quick coupler, brass",
    value_type: "text",
    provenance: {
      source_document_id: "doc-1",
      source_filename: "manifest.html",
      source_type: "html",
      source_page: null,
      source_bbox: null,
      evidence_text: "2 | HX-4410 | Quick coupler, brass",
      extraction_method: "dom:html_dom",
      source_locator: locator,
      source_region_id: "html:table:1:r1:c2",
      anchor_text: "2",
      highlight_text: "Quick coupler, brass",
    },
    validation: { status: "passed", checks: [] },
    review_status: "Verified",
    review_reasons: [],
  };
}

describe("HTML provenance", () => {
  it("is openable without a page number and never shows an invented page", () => {
    const cell = htmlCell();
    expect(canOpenSource(cell)).toBe(true);
    expect(locationLabel(cell)).toBe("Table 1 · row 2");
    expect(cellSourceRequest(cell, "r1")).toMatchObject({
      sourceType: "html",
      regionId: "html:table:1:r1:c2",
      locator,
    });
  });
});

describe("HtmlEvidencePanel", () => {
  beforeEach(() => {
    getContext.mockReset();
  });

  it("shows the section trail, the table with the originating cell marked, and the DOM path", async () => {
    getContext.mockResolvedValue({
      region: null,
      field: null,
      table: {
        candidate_id: "html:table:1",
        headers: ["Line", "Part Number", "Description"],
        rows: [
          [
            { row_index: 0, column_index: 0, text: "1", source_locator: null },
            { row_index: 0, column_index: 1, text: "HX-2201", source_locator: null },
            { row_index: 0, column_index: 2, text: "Hydraulic hose assembly, 2 m", source_locator: null },
          ],
          [
            { row_index: 1, column_index: 0, text: "2", source_locator: null },
            { row_index: 1, column_index: 1, text: "HX-4410", source_locator: null },
            { row_index: 1, column_index: 2, text: "Quick coupler, brass", source_locator: null },
          ],
        ],
        source_locator: null,
        detection_method: "html_dom",
      },
      row_index: 1,
      column_index: 2,
    });
    const request = cellSourceRequest(htmlCell(), "r1");
    render(<HtmlEvidencePanel documentId="doc-1" request={request!} />);

    const marked = await screen.findByText("Quick coupler, brass");
    expect(marked).toHaveAttribute("data-evidence-highlight");
    expect(screen.getByText("Hydraulic hose assembly, 2 m")).not.toHaveAttribute("data-evidence-highlight");
    expect(screen.getByText("Shipment Manifest")).toBeInTheDocument();
    expect(screen.getByText(locator.dom_path)).toBeInTheDocument();
    expect(getContext).toHaveBeenCalledWith("doc-1", "html:table:1:r1:c2");
  });
});
