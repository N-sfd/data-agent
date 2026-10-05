import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DocumentsHome from "@/components/documents/documents-home";
import { deleteDocuments, getDocumentStatusCounts, searchDocuments, startProcessingJob } from "@/lib/documents";
import { downloadExport, getStagingProfile } from "@/lib/staging-workbook";
import type { DocumentSummary } from "@/types/document";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/documents", () => ({
  searchDocuments: vi.fn(),
  getDocumentStatusCounts: vi.fn(),
  deleteDocuments: vi.fn(),
  startProcessingJob: vi.fn(),
}));
vi.mock("@/lib/staging-workbook", () => ({
  getStagingProfile: vi.fn(),
  downloadExport: vi.fn(),
}));

function doc(id: string, name: string, extra: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    document_id: id, original_filename: name, document_type: null, status: "completed", confidence: null,
    uploaded_at: "2026-10-01T10:00:00Z", page_count: 1, fields_extracted: 0, last_updated: "2026-10-01T10:00:00Z",
    staging_status: "staged", ...extra,
  };
}

let rows: DocumentSummary[];
let total: number;

beforeEach(() => {
  vi.clearAllMocks();
  rows = [
    doc("d1", "05_multipage_stress.pdf", { profile_id: "invoice", profile_label: "Invoice", type_label: "Invoice" }),
    doc("d2", "04_international_eur.pdf", { profile_id: "invoice", profile_label: "Invoice", type_label: "Invoice" }),
    doc("d3", "SF1442 Award_N4019223D2803.pdf", { profile_id: "contract_v3", profile_label: "Government Contract", type_label: "SF 1442 Contract Award" }),
    // Named like an invoice, but never staged: no guessed type.
    doc("d4", "invoice_copy.pdf", { staging_status: "not_staged", profile_id: null, profile_label: null, type_label: null }),
  ];
  total = 3209;
  vi.mocked(searchDocuments).mockImplementation(async () => ({ documents: rows, total }));
  vi.mocked(getDocumentStatusCounts).mockImplementation(async () => ({ total, by_status: { review_required: 428, completed: 22 } }));
  vi.mocked(deleteDocuments).mockImplementation(async (ids: string[]) => {
    rows = rows.filter((row) => !ids.includes(row.document_id));
    total -= ids.length;
    return { deleted: ids, not_found: [], forbidden: [], storage_errors: [] };
  });
});

function row(name: string) {
  return screen.getByText(name).closest("tr") as HTMLElement;
}

describe("Documents table", () => {
  it("shows the persisted Type and Profile, never a filename guess, in a wide layout", async () => {
    render(<DocumentsHome />);
    await screen.findByText("05_multipage_stress.pdf");
    expect(screen.getByTestId("documents-home").className).not.toMatch(/max-w-/);
    const headers = screen.getAllByRole("columnheader").map((th) => th.textContent?.trim());
    expect(headers).toEqual(["", "Document", "Type", "Profile", "Status", "Updated", "Actions"]);
    expect(within(row("05_multipage_stress.pdf")).getAllByText("Invoice")).toHaveLength(2);
    expect(within(row("SF1442 Award_N4019223D2803.pdf")).getByText("SF 1442 Contract Award")).toBeTruthy();
    expect(within(row("SF1442 Award_N4019223D2803.pdf")).getByText("Government Contract")).toBeTruthy();
    const unstaged = row("invoice_copy.pdf");
    expect(within(unstaged).queryByText("Invoice")).toBeNull();
    expect(within(unstaged).getByText("Not staged")).toBeTruthy();
    // No internal ids.
    expect(screen.queryByText(/invoice@1|generic_business_document@2|contract_v3/)).toBeNull();
  });

  it("asks before deleting and refreshes the list and counts afterwards", async () => {
    render(<DocumentsHome />);
    await screen.findByText("05_multipage_stress.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Actions for 05_multipage_stress.pdf" }));
    expect(within(screen.getByRole("menu")).getAllByRole("menuitem").map((item) => item.textContent)).toEqual([
      "Open", "Export", "Reprocess", "Delete",
    ]);
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));
    // Nothing is deleted on that click.
    expect(deleteDocuments).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog", { name: "Delete document?" });
    expect(within(dialog).getByText("05_multipage_stress.pdf")).toBeTruthy();
    expect(within(dialog).getByText(/permanently delete the source document, extracted data, staging data/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(deleteDocuments).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Actions for 05_multipage_stress.pdf" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete Document" }));
    await waitFor(() => expect(screen.queryByText("05_multipage_stress.pdf")).toBeNull());
    expect(deleteDocuments).toHaveBeenCalledWith(["d1"]);
    expect(await screen.findByText("3,208")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("1 document deleted");
  });

  it("deletes a multi-selection behind the same confirmation", async () => {
    render(<DocumentsHome />);
    await screen.findByText("05_multipage_stress.pdf");
    fireEvent.click(screen.getByLabelText("Select 05_multipage_stress.pdf"));
    fireEvent.click(screen.getByLabelText("Select 04_international_eur.pdf"));
    const bar = screen.getByRole("region", { name: "Selection" });
    expect(within(bar).getByText("2 selected")).toBeTruthy();
    fireEvent.click(within(bar).getByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog", { name: "Delete 2 documents?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete 2 Documents" }));
    await waitFor(() => expect(screen.queryByText("04_international_eur.pdf")).toBeNull());
    expect(deleteDocuments).toHaveBeenCalledWith(["d1", "d2"]);
    expect(screen.queryByRole("region", { name: "Selection" })).toBeNull();
  });

  it("exports the staging workbook and reprocesses on request", async () => {
    const capability = { capability_id: "x", label: "Invoice Workbook", format: "xlsx" as const, href: "/x", dataset_id: null };
    vi.mocked(getStagingProfile).mockResolvedValue({
      profile_id: "invoice", profile_version: 1, display_name: "Invoice", description: "", document_families: [],
      export_capabilities: [capability], oracle_mapping_capability: "none",
    });
    render(<DocumentsHome />);
    await screen.findByText("05_multipage_stress.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Actions for 05_multipage_stress.pdf" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Export" }));
    await waitFor(() => expect(downloadExport).toHaveBeenCalledWith(capability, "05_multipage_stress"));
    fireEvent.click(screen.getByRole("button", { name: "Actions for invoice_copy.pdf" }));
    expect((screen.getByRole("menuitem", { name: "Export" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("menuitem", { name: "Reprocess" }));
    await waitFor(() => expect(startProcessingJob).toHaveBeenCalledWith("d4"));
  });
});
