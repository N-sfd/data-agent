import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cellSourceRequest } from "@/components/staging/review-status";
import StagingWorkbook from "@/components/staging/staging-workbook";
import { ApiError } from "@/lib/api";
import {
  getStagingWorkbook,
  type CellProvenance,
  type StagingCell,
  type StagingDataset,
  type StagingWorkbook as Workbook,
} from "@/lib/staging-workbook";

vi.mock("@/lib/staging-workbook", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/staging-workbook")>()),
  getStagingWorkbook: vi.fn(),
}));

const getWorkbook = vi.mocked(getStagingWorkbook);

function provenance(overrides: Partial<CellProvenance> = {}): CellProvenance {
  return {
    source_document_id: "doc-1",
    source_filename: "Contract.pdf",
    source_type: "pdf",
    source_page: 3,
    source_bbox: null,
    evidence_text: "10301   RD-541330-SB   0.00",
    extraction_method: "table",
    source_locator: null,
    source_region_id: "clin:2",
    anchor_text: "10301",
    highlight_text: null,
    ...overrides,
  };
}

function cell(
  canonical_field: string,
  display_label: string,
  value: StagingCell["value"],
  review_status: StagingCell["review_status"],
  prov: CellProvenance | null = provenance(),
): StagingCell {
  return {
    canonical_field,
    display_label,
    value,
    raw_value: value == null ? null : String(value),
    value_type: typeof value === "number" ? "money" : "text",
    provenance: value == null ? null : prov,
    validation: { status: "passed", checks: [] },
    review_status,
    review_reasons: review_status === "Missing" ? ["No source-supported value was found for this field."] : [],
  };
}

function dataset(overrides: Partial<StagingDataset> & Pick<StagingDataset, "dataset_id" | "display_name">): StagingDataset {
  return {
    cardinality: "repeating",
    role: "business",
    description: null,
    columns: [],
    records: [],
    identity_fields: [],
    ...overrides,
  };
}

function contractWorkbook(overrides: Partial<Workbook> = {}): Workbook {
  const summaryCells = {
    "contract.contract_number": cell(
      "contract.contract_number",
      "Contract Number",
      "47QRCA25DSF07",
      "Verified",
      provenance({
        source_page: 2,
        evidence_text: "CONTRACT NUMBER -> 47QRCA25DSF07",
        anchor_text: "CONTRACT NUMBER",
        highlight_text: "47QRCA25DSF07",
        source_bbox: [10, 20, 110, 32],
      }),
    ),
    "contract.naics": cell("contract.naics", "NAICS", null, "Missing"),
  };
  return {
    document_id: "doc-1",
    document_filename: "Contract.pdf",
    profile: {
      profile_id: "contract_v3",
      profile_version: 1,
      display_name: "Contract",
      description: "",
      document_families: ["government_contract"],
      export_capabilities: [
        {
          capability_id: "professional_excel",
          label: "Professional Excel (V3 workbook)",
          format: "xlsx",
          href: "/api/documents/doc-1/v3/export.xlsx",
          dataset_id: null,
        },
      ],
      oracle_mapping_capability: "planned",
    },
    outcome: {
      status: "populated",
      title: "Extraction complete",
      message: "2 source-supported record(s) staged.",
      details: [],
      record_count: 2,
      needs_review_count: 0,
    },
    datasets: [
      dataset({
        dataset_id: "contract_summary",
        display_name: "Contract Summary",
        cardinality: "single",
        columns: Object.values(summaryCells).map((c) => ({
          canonical_field: c.canonical_field,
          key: c.canonical_field,
          display_label: c.display_label,
          value_type: "text",
          expected: true,
        })),
        records: [{ record_id: "contract_summary", cells: summaryCells, record_status: "Verified", links_to_dataset: null }],
      }),
      dataset({
        dataset_id: "clins",
        display_name: "CLINs",
        columns: [
          { canonical_field: "contract.clin.clin", key: "clin", display_label: "CLIN", value_type: "code", expected: true },
          { canonical_field: "contract.clin.max_amount", key: "max_amount", display_label: "Max Amount", value_type: "money", expected: false },
        ],
        records: [
          {
            record_id: "clin:2",
            cells: {
              "contract.clin.clin": cell("contract.clin.clin", "CLIN", "10301", "Needs Review"),
              "contract.clin.max_amount": cell(
                "contract.clin.max_amount",
                "Max Amount",
                0,
                "Needs Review",
                provenance({ highlight_text: "0.00" }),
              ),
            },
            record_status: "Needs Review",
            links_to_dataset: null,
          },
        ],
      }),
      dataset({ dataset_id: "source_documents", display_name: "Source Documents", role: "source" }),
    ],
    qa_summary: { verified: 1, needs_review: 2, missing: 1, record_count: 2 },
    processing_metadata: {
      document_family: "government_contract",
      document_family_label: "Government Contract",
      resolution_reasons: [],
      resolved_at: null,
      page_count: 92,
      source_type: "pdf",
      transcription_available: true,
    },
    ...overrides,
  };
}

describe("StagingWorkbook load failures", () => {
  beforeEach(() => {
    getWorkbook.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it("shows a sign-in prompt with an API keys link on 401, without retrying", async () => {
    getWorkbook.mockRejectedValue(new ApiError("Authentication required.", 401));
    render(<StagingWorkbook documentId="doc-1" />);
    expect(await screen.findByText("Sign-in required to view the staging workbook.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "API keys" })).toHaveAttribute("href", "/api-keys");
    expect(getWorkbook).toHaveBeenCalledTimes(1);
  });

  it("explains insufficient permission on 403", async () => {
    getWorkbook.mockRejectedValue(new ApiError("Forbidden", 403));
    render(<StagingWorkbook documentId="doc-1" />);
    expect(
      await screen.findByText("Your access key doesn't have permission to view the staging workbook."),
    ).toBeInTheDocument();
    expect(getWorkbook).toHaveBeenCalledTimes(1);
  });

  it("keeps retrying through a Render cold start instead of giving up", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    getWorkbook
      .mockRejectedValueOnce(new ApiError("Bad Gateway", 502))
      .mockRejectedValueOnce(new Error("Cannot reach the Data Agent API"))
      .mockRejectedValueOnce(new ApiError("Service Unavailable", 503))
      .mockRejectedValueOnce(new ApiError("Service Unavailable", 503))
      .mockResolvedValue(contractWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);
    await vi.advanceTimersByTimeAsync(40_000);
    await vi.waitFor(() => expect(getWorkbook.mock.calls.length).toBeGreaterThanOrEqual(5));
    expect(screen.queryByText("Unable to load the staging workbook.")).toBeNull();
  });

  it("fails fast on 404", async () => {
    getWorkbook.mockRejectedValue(new ApiError("Document not found", 404));
    render(<StagingWorkbook documentId="doc-1" />);
    expect(await screen.findByText("Unable to load the staging workbook.")).toBeInTheDocument();
    expect(getWorkbook).toHaveBeenCalledTimes(1);
  });
});

describe("StagingWorkbook rendering", () => {
  beforeEach(() => {
    getWorkbook.mockReset();
  });

  it("renders the profile's own datasets as tabs and opens on the first with values", async () => {
    getWorkbook.mockResolvedValue(contractWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);

    expect(await screen.findByText("Contract")).toBeInTheDocument();
    expect(screen.getByText("(contract_v3@1)")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /CLINs/ })).toBeInTheDocument();
    // Single-record dataset renders as a field list with the Missing state.
    expect(screen.getByText("47QRCA25DSF07")).toBeInTheDocument();
    expect(screen.getByText("Missing")).toBeInTheDocument();
    // No banner for a clean, populated outcome.
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("renders a different profile from metadata alone", async () => {
    getWorkbook.mockResolvedValue(
      contractWorkbook({
        profile: {
          ...contractWorkbook().profile,
          profile_id: "generic_business_document",
          display_name: "Generic Business Document",
        },
        datasets: [
          dataset({
            dataset_id: "key_fields",
            display_name: "Key Fields",
            columns: [
              { canonical_field: "document.field.name", key: "name", display_label: "Field", value_type: "text", expected: false },
              { canonical_field: "document.field.value", key: "value", display_label: "Value", value_type: "text", expected: true },
            ],
            records: [
              {
                record_id: "field:1",
                cells: {
                  "document.field.name": cell("document.field.name", "Field", "Email", "Verified"),
                  "document.field.value": cell("document.field.value", "Value", "billing@example.com", "Verified"),
                },
                record_status: "Verified",
                links_to_dataset: null,
              },
            ],
          }),
        ],
      }),
    );
    render(<StagingWorkbook documentId="doc-1" />);

    expect(await screen.findByText("Generic Business Document")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Key Fields/ })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /CLINs/ })).toBeNull();
    expect(screen.getByText("billing@example.com")).toBeInTheDocument();
  });

  it("opens source verification with the clicked CELL's provenance, not the row's", async () => {
    getWorkbook.mockResolvedValue(contractWorkbook());
    const onOpenSource = vi.fn();
    render(<StagingWorkbook documentId="doc-1" onOpenSource={onOpenSource} />);

    fireEvent.click(await screen.findByRole("tab", { name: /CLINs/ }));
    fireEvent.click(screen.getByRole("button", { name: "0.00" }));

    expect(onOpenSource).toHaveBeenCalledWith(
      expect.objectContaining({
        pageNumber: 3,
        highlightText: "0.00",
        anchorText: "10301",
        label: "Max Amount",
        reviewStatus: "Needs Review",
      }),
    );
  });

  it("explains a PDF Portfolio and opens Source Documents instead of a blank workbook", async () => {
    const base = contractWorkbook();
    getWorkbook.mockResolvedValue({
      ...base,
      outcome: {
        status: "special_source",
        title: "PDF Portfolio: embedded documents need extraction",
        message: "This file is an Adobe PDF Portfolio.",
        details: ["SF1442 Award.pdf"],
        record_count: 0,
        needs_review_count: 0,
      },
      datasets: [
        dataset({
          dataset_id: "source_documents",
          display_name: "Source Documents",
          role: "source",
          columns: [{ canonical_field: "source.extraction_status", key: "s", display_label: "Extraction Status", value_type: "text", expected: false }],
          records: [
            {
              record_id: "source:1",
              cells: {
                "source.extraction_status": cell("source.extraction_status", "Extraction Status", "Not extracted (embedded file)", null, null),
              },
              record_status: null,
              links_to_dataset: null,
            },
          ],
        }),
      ],
    });
    render(<StagingWorkbook documentId="doc-1" />);

    expect(await screen.findByText("PDF Portfolio: embedded documents need extraction")).toBeInTheDocument();
    expect(screen.getByText("Not extracted (embedded file)")).toBeInTheDocument();
    expect(getWorkbook).toHaveBeenCalledTimes(1);
  });
});

describe("cellSourceRequest", () => {
  it("carries the cell's anchor, highlight and region", () => {
    const request = cellSourceRequest(
      cell("contract.contract_number", "Contract Number", "47QRCA25DSF07", "Verified", provenance({
        source_page: 2,
        anchor_text: "CONTRACT NUMBER",
        highlight_text: "47QRCA25DSF07",
        source_bbox: [1, 2, 3, 4],
      })),
      "id-1",
    );
    expect(request).toMatchObject({
      pageNumber: 2,
      anchorText: "CONTRACT NUMBER",
      highlightText: "47QRCA25DSF07",
      region: [1, 2, 3, 4],
    });
  });

  it("is null for values without a source page (system facts)", () => {
    expect(
      cellSourceRequest(
        cell("document.page_count", "Pages", 3, "Verified", provenance({ source_type: "system", source_page: null })),
        "id-2",
      ),
    ).toBeNull();
  });
});
