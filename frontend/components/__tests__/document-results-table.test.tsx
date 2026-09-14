import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { deleteDocumentMock, pushMock } = vi.hoisted(() => ({
  deleteDocumentMock: vi.fn(),
  pushMock: vi.fn(),
}));

vi.mock("@/lib/documents", () => ({
  deleteDocument: deleteDocumentMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import DocumentResultsTable from "@/components/document-results-table";
import type { DocumentSummary } from "@/types/document";

function makeDoc(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    document_id: "doc-1",
    original_filename: "invoice.pdf",
    document_type: "Purchase Order",
    counterparty: null,
    effective_date: null,
    expiration_date: null,
    contract_value: null,
    confidence: null,
    repository_status: null,
    relationship: null,
    source_status: "available",
    status: "completed",
    last_updated: new Date().toISOString(),
    ...overrides,
  } as DocumentSummary;
}

describe("DocumentResultsTable repository mode", () => {
  beforeEach(() => {
    deleteDocumentMock.mockReset();
    pushMock.mockReset();
  });

  it("navigates to the document on row click", () => {
    render(
      <DocumentResultsTable
        documents={[makeDoc()]}
        emptyMessage="none"
        repositoryMode
      />,
    );

    fireEvent.click(screen.getByText("invoice.pdf"));
    expect(pushMock).toHaveBeenCalledWith(
      "/extraction/new?documentId=doc-1",
    );
  });

  it("deletes a single document after confirming in the modal", async () => {
    deleteDocumentMock.mockResolvedValue(undefined);
    const onDeleted = vi.fn();

    render(
      <DocumentResultsTable
        documents={[makeDoc()]}
        emptyMessage="none"
        repositoryMode
        onDeleted={onDeleted}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /delete invoice.pdf/i }));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteDocumentMock).toHaveBeenCalledWith("doc-1");
      expect(onDeleted).toHaveBeenCalledWith(["doc-1"]);
    });

    // Row click was never triggered by the delete button/modal clicks.
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("does not delete when the modal is cancelled", () => {
    render(
      <DocumentResultsTable
        documents={[makeDoc()]}
        emptyMessage="none"
        repositoryMode
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /delete invoice.pdf/i }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(deleteDocumentMock).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("selects documents and bulk-deletes them", async () => {
    deleteDocumentMock.mockResolvedValue(undefined);
    const onDeleted = vi.fn();
    const docs = [makeDoc({ document_id: "doc-1" }), makeDoc({ document_id: "doc-2", original_filename: "contract.pdf" })];

    render(
      <DocumentResultsTable
        documents={docs}
        emptyMessage="none"
        repositoryMode
        onDeleted={onDeleted}
      />,
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "Select all documents on this page" }));

    expect(screen.getByText("2 selected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete 2" }));

    await waitFor(() => {
      expect(deleteDocumentMock).toHaveBeenCalledWith("doc-1");
      expect(deleteDocumentMock).toHaveBeenCalledWith("doc-2");
      expect(onDeleted).toHaveBeenCalledWith(
        expect.arrayContaining(["doc-1", "doc-2"]),
      );
    });
  });

  it("surfaces a failure without removing the document from selection", async () => {
    deleteDocumentMock.mockRejectedValue(new Error("Permission denied: documents.delete"));

    render(
      <DocumentResultsTable
        documents={[makeDoc()]}
        emptyMessage="none"
        repositoryMode
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /delete invoice.pdf/i }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(
        screen.getByText(/Couldn't delete "invoice.pdf": Permission denied/i),
      ).toBeInTheDocument();
    });
  });

  it("does not show selection/delete affordances outside repository mode", () => {
    render(
      <DocumentResultsTable documents={[makeDoc()]} emptyMessage="none" />,
    );

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /delete/i }),
    ).not.toBeInTheDocument();
  });
});
