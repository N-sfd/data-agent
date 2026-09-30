import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("offers to drop a rejected saved key on 401, then loads without it", async () => {
    window.localStorage.setItem("data-agent-access-token", "stale-key");
    getWorkbook
      .mockRejectedValueOnce(new ApiError("Invalid bearer credential.", 401))
      .mockRejectedValueOnce(new ApiError("Not found", 404));
    render(<StagingWorkbook documentId="doc-1" />);
    expect(
      await screen.findByText("The access key saved in this browser is no longer valid."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /api keys/i })).toBeNull();
    expect(getWorkbook).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Remove saved key and retry" }));
    await waitFor(() => expect(getWorkbook).toHaveBeenCalledTimes(2));
    expect(window.localStorage.getItem("data-agent-access-token")).toBeNull();
  });

  it("explains a too-narrow saved key on 403", async () => {
    getWorkbook.mockRejectedValue(new ApiError("Forbidden", 403));
    render(<StagingWorkbook documentId="doc-1" />);
    expect(
      await screen.findByText("The access key saved in this browser can't open this workbook."),
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

    expect(await screen.findAllByText("Contract")).not.toHaveLength(0);
    expect(screen.getByText("(contract_v3@1)")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "CLINs" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Contract Summary" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Contract Summary" }));
    expect(screen.getByText("47QRCA25DSF07")).toBeInTheDocument();
    expect(screen.getByText("Missing information")).toBeInTheDocument();
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

describe("StagingWorkbook presentation", () => {
  beforeEach(() => getWorkbook.mockReset());

  function genericWorkbook(): Workbook {
    const base = contractWorkbook();
    const keyCell = cell("document.field.value", "Value", "516522", "Verified");
    return {
      ...base,
      profile: { ...base.profile, profile_id: "generic_business_document", profile_version: 2, display_name: "Generic" },
      datasets: [
        dataset({
          dataset_id: "document_summary",
          display_name: "Document Summary",
          cardinality: "single",
          records: [{ record_id: "s", cells: { "document.document_type": cell("document.document_type", "Document Type", "Certificate", "Verified") }, record_status: "Verified", links_to_dataset: null }],
        }),
        dataset({
          dataset_id: "key_fields",
          display_name: "Key Fields",
          records: [{ record_id: "k", cells: { "document.field.value": keyCell }, record_status: "Verified", links_to_dataset: null }],
        }),
        dataset({ dataset_id: "contacts", display_name: "Contacts" }),
        dataset({ dataset_id: "line_items", display_name: "Line Items" }),
        dataset({ dataset_id: "other_tables", display_name: "Other Tables" }),
        dataset({ dataset_id: "all_fields", display_name: "All Fields" }),
      ],
    };
  }

  it("shows Overview / Tables labels and hides empty Contacts and Line Items for the generic profile", async () => {
    getWorkbook.mockResolvedValue(genericWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);
    const tabs = await screen.findByRole("tablist", { name: "Document sections" });
    const labels = Array.from(tabs.querySelectorAll("button")).map((b) => b.getAttribute("aria-label"));
    expect(labels).toContain("Document Summary");
    expect(labels).toContain("Other Information");
    expect(labels?.join(" ")).not.toMatch(/Key Fields|All Fields|Source Documents|QA Review/);
  });

  it("names the source view Source", async () => {
    getWorkbook.mockResolvedValue(genericWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);
    expect(await screen.findByRole("tab", { name: "Source" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Source & Transcript" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Key Fields" })).toBeNull();
  });
});

describe("Academic transcript presentation", () => {
  beforeEach(() => getWorkbook.mockReset());

  const F = {
    name: "transcript.field.name",
    value: "transcript.field.value",
    category: "transcript.field.category",
    sourceLabel: "transcript.field.source_label",
    fieldId: "transcript.field.field_id",
  };

  function fieldRow(id: string, name: string, value: string, category: string, fieldId: string, sourceLabel: string) {
    const prov = provenance({
      source_filename: "transcript.png",
      source_type: "image",
      source_page: 1,
      evidence_text: `${sourceLabel} : ${value}`,
      extraction_method: "ocr:label_value",
      highlight_text: value,
      source_bbox: [10, 20, 90, 30],
      ocr_confidence: 0.93,
    });
    return {
      record_id: id,
      cells: {
        [F.name]: cell(F.name, "Field", name, "Verified", prov),
        [F.value]: cell(F.value, "Value", value, "Verified", prov),
        [F.category]: cell(F.category, "Category", category, null, null),
        [F.sourceLabel]: cell(F.sourceLabel, "Source Label", sourceLabel, null, null),
        [F.fieldId]: cell(F.fieldId, "Field ID", fieldId, null, null),
      },
      record_status: "Verified" as const,
      links_to_dataset: null,
    };
  }

  function transcriptWorkbook(): Workbook {
    const base = contractWorkbook();
    const fieldColumns = [F.name, F.value, F.category, F.sourceLabel, F.fieldId].map((id) => ({
      canonical_field: id,
      key: id,
      display_label: id,
      value_type: "text",
      expected: false,
    }));
    const student = [
      fieldRow("f1", "Student Name", "Jordan Example", "Student Information", "transcript.student.name", "Name"),
      fieldRow(
        "f2",
        "Program / Degree",
        "Bachelor of Science in Computer Science",
        "Program Information",
        "transcript.program.program",
        "Program / Degree Name",
      ),
    ];
    const gpa = fieldRow("s1", "Cumulative GPA", "3.72", "Academic Summary", "transcript.summary.cumulative_gpa", "CGPA");
    const courseProv = provenance({ source_page: 1, evidence_text: "I   ENG101   English Composition   3   A-", extraction_method: "ocr:course_table" });
    const course = {
      record_id: "c1",
      cells: {
        "transcript.course.code": cell("transcript.course.code", "Course Code", "ENG101", "Verified", courseProv),
        "transcript.course.title": cell("transcript.course.title", "Course Title", "English Composition", "Verified", courseProv),
        "transcript.course.grade": cell("transcript.course.grade", "Grade", "A-", "Verified", courseProv),
        "transcript.course.extra_1": cell("transcript.course.extra_1", "Additional Value", null, null),
      },
      record_status: "Verified" as const,
      links_to_dataset: null,
    };
    return {
      ...base,
      document_filename: "transcript.png",
      profile: { ...base.profile, profile_id: "academic_transcript", profile_version: 1, display_name: "Academic Transcript" },
      datasets: [
        dataset({ dataset_id: "student_program", display_name: "Student & Program", columns: fieldColumns, records: student }),
        dataset({
          dataset_id: "academic_record",
          display_name: "Academic Record",
          columns: ["code", "title", "grade", "extra_1"].map((slot) => ({
            canonical_field: `transcript.course.${slot}`,
            key: slot,
            display_label: slot === "code" ? "Course Code" : slot === "title" ? "Course Title" : slot === "grade" ? "Grade" : "Additional Value",
            value_type: "text",
            expected: false,
          })),
          records: [course],
        }),
        dataset({ dataset_id: "academic_summary", display_name: "Academic Summary", columns: fieldColumns, records: [gpa] }),
        dataset({ dataset_id: "other_information", display_name: "Other Information", columns: fieldColumns }),
        dataset({
          dataset_id: "all_fields",
          display_name: "All Fields",
          columns: fieldColumns,
          records: [...student, gpa].map((r) => ({ ...r, record_id: `all:${r.record_id}` })),
        }),
        dataset({ dataset_id: "qa_review", display_name: "Review", role: "qa" }),
      ],
    };
  }

  it("uses content-derived sections and a Source view", async () => {
    getWorkbook.mockResolvedValue(transcriptWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);
    const sections = await screen.findByRole("tablist", { name: "Document sections" });
    const labels = Array.from(sections.querySelectorAll("button")).map((b) => b.getAttribute("aria-label"));
    expect(labels).toContain("Student & Program");
    expect(labels).toContain("Academic Record");
    expect(labels).toContain("Other Information");
    expect(labels).not.toContain("All Fields");
    expect(screen.getByRole("tab", { name: "Staging Workbook" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Source" })).toBeInTheDocument();
    for (const generic of ["Key Fields", "Tables", "Source Documents", "QA Review"]) {
      expect(screen.queryByRole("tab", { name: new RegExp(`^${generic}$`) })).toBeNull();
    }
    expect(screen.getByText("Jordan Example")).toBeInTheDocument();
    expect(screen.getByText("Bachelor of Science in Computer Science")).toBeInTheDocument();
    expect(screen.queryByText(/academic_transcript@1/)).toBeNull();
  });

  it("shows All Fields as FIELD | VALUE | CATEGORY, category last", async () => {
    getWorkbook.mockResolvedValue(transcriptWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);
    fireEvent.click(await screen.findByRole("tab", { name: "Other Information" }));
    const headers = Array.from(document.querySelectorAll("th")).map((th) => th.textContent);
    expect(headers).toEqual(["Field", "Value", "Category"]);
    for (const hidden of ["Type", "Status", "Source", "Evidence", "Found By", "Extraction Method", "Location"]) {
      expect(headers).not.toContain(hidden);
    }
  });

  it("opens a value's evidence with humanized technical details", async () => {
    getWorkbook.mockResolvedValue(transcriptWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);
    fireEvent.click(await screen.findByRole("tab", { name: /Student & Program/ }));
    fireEvent.click(screen.getByRole("button", { name: "Jordan Example" }));
    const dialog = screen.getByRole("dialog", { name: "Evidence" });
    expect(dialog).toHaveTextContent("Source Evidence");
    expect(dialog).toHaveTextContent("Page 1");
    expect(dialog).toHaveTextContent("Name : Jordan Example");
    expect(dialog).toHaveTextContent("OCR · Label / value pair");
    expect(dialog).toHaveTextContent("transcript.student.name");
    expect(dialog).not.toHaveTextContent("label_value");
    expect(screen.getByRole("button", { name: "View in Document" })).toBeInTheDocument();
  });

  it("shows only the academic record's printed columns, never empty fallbacks", async () => {
    getWorkbook.mockResolvedValue(transcriptWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);
    fireEvent.click(await screen.findByRole("tab", { name: /Academic Record/ }));
    const headers = Array.from(document.querySelectorAll("thead th")).map((th) => th.textContent);
    expect(headers).toEqual(["Course Code", "Course Title", "Grade"]);
    expect(screen.getByRole("textbox", { name: "Search academic record" })).toBeInTheDocument();
  });
});

describe("Invoice presentation", () => {
  beforeEach(() => getWorkbook.mockReset());

  function invoiceWorkbook(): Workbook {
    const base = contractWorkbook();
    const lineCells = {
      "invoice.line.description": cell("invoice.line.description", "Description", "Premium copy paper", "Verified"),
      "invoice.line.amount": cell("invoice.line.amount", "Line Amount", 212.5, "Verified"),
      "invoice.line.source_table": cell("invoice.line.source_table", "Table", "Table 1 (page 1)", "Verified"),
    };
    const field = {
      record_id: "field:1",
      cells: {
        "invoice.field.name": cell("invoice.field.name", "Field", "Invoice Number", "Verified"),
        "invoice.field.value": cell("invoice.field.value", "Value", "NS-2026-1048", "Verified"),
        "invoice.field.category": cell("invoice.field.category", "Category", "Invoice Summary", "Verified"),
        "invoice.field.found_by": cell("invoice.field.found_by", "Found By", "invoice field", "Verified"),
        "invoice.field.value_type": cell("invoice.field.value_type", "Type", "code", "Verified"),
      },
      record_status: "Verified" as const,
      links_to_dataset: null,
    };
    return {
      ...base,
      profile: { ...base.profile, profile_id: "invoice", profile_version: 1, display_name: "Invoice" },
      datasets: [
        dataset({
          dataset_id: "invoice_lines",
          display_name: "Invoice Lines",
          columns: [
            { canonical_field: "invoice.line.description", key: "description", display_label: "Description", value_type: "text", expected: false },
            { canonical_field: "invoice.line.amount", key: "amount", display_label: "Line Amount", value_type: "money", expected: true },
            { canonical_field: "invoice.line.source_table", key: "source_table", display_label: "Table", value_type: "text", expected: false },
          ],
          records: [{ record_id: "line:1", cells: lineCells, record_status: "Verified", links_to_dataset: null }],
        }),
        dataset({
          dataset_id: "all_fields",
          display_name: "All Fields",
          columns: [
            { canonical_field: "invoice.field.category", key: "category", display_label: "Category", value_type: "text", expected: false },
            { canonical_field: "invoice.field.name", key: "name", display_label: "Field", value_type: "text", expected: false },
            { canonical_field: "invoice.field.value", key: "value", display_label: "Value", value_type: "text", expected: true },
            { canonical_field: "invoice.field.found_by", key: "found_by", display_label: "Found By", value_type: "text", expected: false },
          ],
          records: [field],
        }),
      ],
    };
  }

  it("opens on Line Items and hides Table / Found By from the primary surfaces", async () => {
    getWorkbook.mockResolvedValue(invoiceWorkbook());
    render(<StagingWorkbook documentId="doc-1" />);
    expect(await screen.findByRole("tab", { name: "Line Items", selected: true })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Invoice Summary" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Source Documents" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Table" })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Other Information" }));
    const headers = Array.from(document.querySelectorAll("th")).map((header) => header.textContent);
    expect(headers).toContain("Field");
    expect(headers).toContain("Value");
    expect(headers.indexOf("Category")).toBe(headers.length - 1);
    expect(headers).not.toContain("Found By");
    expect(screen.queryByText("Found By")).toBeNull();
  });
});

describe("FAR staging navigation", () => {
  beforeEach(() => getWorkbook.mockReset());

  it("shows five primary tabs with Overview last and Transform opening on Final Output", async () => {
    const base = contractWorkbook();
    getWorkbook.mockResolvedValue({
      ...base,
      profile: { ...base.profile, profile_id: "far_part_52", profile_version: 1, display_name: "FAR Part 52" },
      datasets: [
        dataset({ dataset_id: "far_sections", display_name: "FAR Sections", records: [] }),
        dataset({ dataset_id: "far_clauses", display_name: "Clauses & Provisions", records: [] }),
        dataset({ dataset_id: "far_alternates", display_name: "Alternates", records: [] }),
        dataset({ dataset_id: "far_references", display_name: "FAR References", records: [] }),
        dataset({ dataset_id: "far_canonical", display_name: "Canonical Model", records: [] }),
        dataset({ dataset_id: "far_oracle_output_map", display_name: "Oracle Output Map", records: [] }),
        dataset({ dataset_id: "far_business", display_name: "Business Export", records: [] }),
        dataset({ dataset_id: "all_fields", display_name: "All Fields", records: [] }),
        dataset({ dataset_id: "source_documents", display_name: "Source Documents", role: "source", records: [] }),
        dataset({ dataset_id: "qa_review", display_name: "QA Review", role: "qa", records: [] }),
        dataset({
          dataset_id: "far_overview",
          display_name: "Overview",
          cardinality: "single",
          records: [],
        }),
      ],
    });
    render(<StagingWorkbook documentId="doc-1" />);
    const nav = await screen.findByRole("tablist", { name: "Document sections" });
    const labels = Array.from(nav.querySelectorAll("[role='tab']")).map((tab) => tab.getAttribute("aria-label"));
    expect(labels?.[0]).toBe("Other Information");
    expect(labels).not.toContain("FAR Sections");
    expect(labels).not.toContain("Source Documents");
    expect(labels).not.toContain("QA Review");
    expect(screen.queryByRole("tab", { name: "FAR Sections" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Canonical Model" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Oracle Output Map" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Source Documents" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "QA Review" })).toBeNull();
    expect(screen.getByRole("tab", { name: "Source" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Source" })).toBeInTheDocument();
  });
});
