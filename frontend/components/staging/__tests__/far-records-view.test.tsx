import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FarRecordsView from "@/components/staging/far-records-view";
import { FAR_COLUMNS, alternateSummary, farHeading, filterFarGroups, groupFarRecords } from "@/lib/far-records";
import { getStagingRecord, type StagingCell, type StagingDataset, type StagingRecord } from "@/lib/staging-workbook";

vi.mock("@/lib/staging-workbook", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/staging-workbook")>()),
  getStagingRecord: vi.fn(),
}));

function cell(key: string, value: string | null, status: StagingCell["review_status"] = "Verified"): StagingCell {
  return {
    canonical_field: `far.record.${key}`,
    display_label: FAR_COLUMNS.find((column) => column.key === key)?.label ?? key,
    value,
    raw_value: value,
    value_type: "text",
    provenance: null,
    validation: { status: "passed", checks: [] },
    review_status: value == null ? null : status,
    review_reasons: [],
  };
}

// Columns no fixture record fills (hidden in the grid): Part 52 has no
// Part / Subpart titles here, no forms, no cross references, no section text.
const EMPTY_IN_FIXTURE = [
  "cross_references", "section_text", "far_part_title", "far_subpart_title",
  "form_number", "form_name", "form_type", "prescribing_reference", "form_usage", "supersession",
];

const LONG_TEXT = "Prohibition on Requiring Certain Internal Confidentiality Agreements (Jan 2017)\n(a) The Contractor shall not require employees ... ".repeat(20);

function record(id: string, values: Record<string, string | null>, status: StagingRecord["record_status"] = "Verified"): StagingRecord {
  return {
    record_id: id,
    record_status: status,
    links_to_dataset: null,
    cells: Object.fromEntries(FAR_COLUMNS.map((column) => [`far.record.${column.key}`, cell(column.key, values[column.key] ?? null)])),
  };
}

function farDataset(extra: StagingRecord[] = []): StagingDataset {
  const records = [
    record("r1", { far_number: "52.203-19", title: "Prohibition on Requiring Certain Internal Confidentiality Agreements or Statements",
      record_type: "Clause", far_part: "Part 52", far_subpart: "Subpart 52.2", far_section: "52.203", record_status: "Active",
      revision_date: "Jan 2017", description: "Prohibition … (Jan 2017)", prescription: "As prescribed in 3.909-3(b), insert the following clause:",
      prescription_reference: "3.909-3(b)", clause_text: LONG_TEXT, source_reference: "part_52.html › Subpart 52.2 › 52.203-19 · #FAR_52_203_19" }),
    record("r2", { far_number: "52.215-1", title: "Instructions to Offerors-Competitive Acquisition", record_type: "Provision",
      far_part: "Part 52", far_subpart: "Subpart 52.2", far_section: "52.215", record_status: "Active", revision_date: "Nov 2021",
      provision_text: "Instructions to Offerors (Nov 2021)\n(a) Definitions." }),
    record("r3", { far_number: "52.215-1", title: "Instructions to Offerors-Competitive Acquisition", record_type: "Provision",
      alternate: "Alternate I", description: "Alternate I (Oct 1997)", prescription: "As prescribed in 15.209(a)(1), substitute …",
      prescription_reference: "15.209(a)(1)", provision_text: "(f)(4) The Government intends to evaluate proposals after discussions." }, "Needs Review"),
    record("r4", { far_number: "52.203-1", title: "[Reserved]", record_type: "Reserved", record_status: "Reserved" }),
    ...extra,
  ];
  return {
    dataset_id: "far_records",
    display_name: "FAR Clauses & Provisions",
    cardinality: "repeating",
    role: "business",
    description: null,
    columns: FAR_COLUMNS.map((column) => ({ canonical_field: `far.record.${column.key}`, key: column.key, display_label: column.label, value_type: "text", expected: false })),
    records,
    identity_fields: [],
    compact: true,
    full_text: true,
  };
}

describe("FAR record grouping", () => {
  it("keeps alternates with their FAR record", () => {
    const groups = groupFarRecords(farDataset().records);
    expect(groups.map((group) => group.record.record_id)).toEqual(["r1", "r2", "r4"]);
    expect(groups[1].alternates.map((alternate) => alternate.record_id)).toEqual(["r3"]);
    expect(alternateSummary(groups[1])).toBe("Alternate I");
    // An alternate's review state is its record's.
    expect(groups[1].status).toBe("Needs Review");
  });

  it("filters by type, review status and text inside alternates", () => {
    const groups = groupFarRecords(farDataset().records);
    expect(filterFarGroups(groups, { query: "", type: "Clause", review: "all" }).length).toBe(1);
    expect(filterFarGroups(groups, { query: "", type: "all", review: "Needs Review" }).map((g) => g.record.record_id)).toEqual(["r2"]);
    expect(filterFarGroups(groups, { query: "evaluate proposals", type: "all", review: "all" }).map((g) => g.record.record_id)).toEqual(["r2"]);
  });

  it("names the Part as the source does", () => {
    expect(farHeading("Part 52 - Solicitation Provisions and Contract Clauses")).toBe(
      "FAR Part 52 — Solicitation Provisions and Contract Clauses",
    );
    expect(farHeading(null)).toBe("FAR Clauses & Provisions");
  });
});

describe("FarRecordsView", () => {
  beforeEach(() => {
    vi.mocked(getStagingRecord).mockResolvedValue({
      ...farDataset().records[0],
      cells: {
        ...farDataset().records[0].cells,
        "far.record.description": {
          ...cell("description", "Prohibition … (Jan 2017)"),
          provenance: {
            source_document_id: "d", source_filename: "part_52.html", source_type: "html", source_page: null, source_bbox: null,
            evidence_text: "x", extraction_method: "far_dom",
            source_locator: { dom_path: "/html/body/article[3]", element_id: "FAR_52_203_19", section_path: [], table_index: null, row_index: null, column_index: null, sheet_name: null, cell_ref: null },
            source_region_id: null, anchor_text: null, highlight_text: null,
          },
        },
      },
    });
  });

  function renderView(extra: StagingRecord[] = []) {
    return render(
      <FarRecordsView documentId="d" dataset={farDataset(extra)} filename="part_52.html" partHeading="Part 52 - Solicitation Provisions and Contract Clauses" />,
    );
  }

  it("shows the local heading and a compact grid in the specified column order", () => {
    renderView();
    expect(screen.getByRole("heading", { name: "FAR Part 52 — Solicitation Provisions and Contract Clauses" })).toBeTruthy();
    expect(screen.getByText(/3 FAR records · 1 alternates within them · extracted from part_52.html/)).toBeTruthy();
    // The first header is the select-all checkbox column.
    const headers = screen.getAllByRole("columnheader").slice(1).map((header) => header.textContent);
    // Specified order; a column no record fills (here Cross References,
    // Section Text) is left out.
    const shown = FAR_COLUMNS.filter((column) => !EMPTY_IN_FIXTURE.includes(column.key));
    expect(headers.slice(0, shown.length)).toEqual(shown.map((column) => column.label));
    expect(headers).not.toContain("Cross References");
    // No technical fields in the business grid.
    for (const technical of ["Confidence", "Extraction Method", "Field ID", "Evidence", "Location"]) {
      expect(headers).not.toContain(technical);
    }
  });

  it("keeps rows one line high: long values are ellipsized, FAR Number and Title frozen", () => {
    renderView();
    const row = screen.getByRole("row", { name: /52\.203-19/ });
    const cells = within(row).getAllByRole("cell");
    for (const td of cells) expect(td.className).toContain("h-8");
    // cells[0] is the row-selection checkbox column (36px, frozen at 0).
    const visible = FAR_COLUMNS.filter((column) => !EMPTY_IN_FIXTURE.includes(column.key));
    const clauseText = cells[1 + visible.findIndex((column) => column.key === "clause_text")];
    expect(clauseText.querySelector("span.truncate")).toBeTruthy();
    expect(cells[0].className).toContain("sticky");
    expect(cells[1].className).toContain("sticky");
    expect(cells[1].style.left).toBe("36px");
    expect(cells[2].className).toContain("sticky");
    // Check column (36) + FAR Number, widened to fit its header (116).
    expect(cells[2].style.left).toBe("152px");
    expect(cells[3].className).not.toContain("sticky");
    const header = screen.getAllByRole("columnheader")[0];
    expect(header.className).toContain("sticky");
    expect(header.className).toContain("top-0");
  });

  it("lists alternates under their record, not as rows", () => {
    renderView();
    expect(screen.getAllByRole("row", { name: /52\.215-1/ })).toHaveLength(1);
    const group = screen.getByRole("group", { name: "Filter by record type" });
    const chips = within(group).getAllByRole("button").map((button) => button.textContent);
    expect(chips).toEqual(["All 3", "Clause 1", "Provision 1", "Reserved 1"]);
  });

  it("filters by type chip and the Review dropdown", () => {
    renderView();
    fireEvent.click(screen.getByRole("button", { name: /Reserved/ }));
    expect(screen.getAllByRole("row")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: /^All/ }));
    fireEvent.change(screen.getByLabelText("Review status"), { target: { value: "Needs Review" } });
    expect(screen.getByRole("row", { name: /52\.215-1/ })).toBeTruthy();
    expect(screen.queryByRole("row", { name: /52\.203-19/ })).toBeNull();
  });

  it("pages at 100 records", () => {
    const extra = Array.from({ length: 120 }, (_, index) =>
      record(`x${index}`, { far_number: `52.299-${index}`, title: `Filler ${index}`, record_type: "Clause" }),
    );
    renderView(extra);
    expect(screen.getAllByRole("row")).toHaveLength(101);
    expect(screen.getByText(/1–100 of 123/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getAllByRole("row")).toHaveLength(24);
  }, 20_000);

  it("opens the complete record in a drawer with Enter (a click selects a cell)", async () => {
    renderView();
    const row = screen.getByRole("row", { name: /52\.203-19/ });
    fireEvent.click(within(row).getAllByRole("cell")[2]);
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.keyDown(row, { key: "Enter" });
    const drawer = screen.getByRole("dialog", { name: "52.203-19 details" });
    expect(within(drawer).getByRole("heading", { name: /52\.203-19 — Prohibition on Requiring/ })).toBeTruthy();
    expect(within(drawer).getByText("Clause · Part 52 · Subpart 52.2 · Section 52.203 · Jan 2017")).toBeTruthy();
    expect(within(drawer).getByText("3.909-3(b)")).toBeTruthy();
    expect(within(drawer).getByRole("heading", { name: "Clause Text" })).toBeTruthy();
    // Full text, as paragraphs — not ellipsized.
    expect(within(drawer).getAllByText(/The Contractor shall not require employees/).length).toBeGreaterThan(1);
    expect(await within(drawer).findByText(/part_52.html → #FAR_52_203_19/)).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows a record's alternates in its drawer", () => {
    renderView();
    fireEvent.click(screen.getAllByRole("button", { name: "Details" })[1]);
    const drawer = screen.getByRole("dialog", { name: "52.215-1 details" });
    expect(within(drawer).getByText("Alternate I (Oct 1997)")).toBeTruthy();
    expect(within(drawer).getByText(/Prescription reference 15.209\(a\)\(1\)/)).toBeTruthy();
    expect(within(drawer).getByText(/The Government intends to evaluate proposals/)).toBeTruthy();
  });
});
