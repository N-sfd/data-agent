import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SourceVerificationPanel, {
  type SourceViewRequest,
} from "@/components/source-verification-panel";

const { getPageRenderMock, getDocumentPagesMock } = vi.hoisted(() => ({
  getPageRenderMock: vi.fn(),
  getDocumentPagesMock: vi.fn(),
}));

vi.mock("@/lib/documents", () => ({
  getPageRender: getPageRenderMock,
  getDocumentPages: getDocumentPagesMock,
}));

function makeRender(overrides: Partial<{
  page_number: number;
  image_data_url: string;
  page_width: number;
  page_height: number;
  highlight: { x0: number; y0: number; x1: number; y1: number } | null;
}> = {}) {
  return {
    page_number: 1,
    image_data_url: "data:image/png;base64,AAAA",
    page_width: 612,
    page_height: 792,
    highlight: null,
    ...overrides,
  };
}

function request(overrides: Partial<SourceViewRequest> = {}): SourceViewRequest {
  return {
    id: "contract_number",
    pageNumber: 1,
    highlightText: "Contract Number: W912DR-26-C-0042",
    label: "contract_number",
    value: "W912DR-26-C-0042",
    confidence: 0.9,
    verified: true,
    ...overrides,
  };
}

describe("SourceVerificationPanel", () => {
  beforeEach(() => {
    getPageRenderMock.mockReset();
    getDocumentPagesMock.mockReset();
  });

  it("shows the source page when a render is available", async () => {
    getPageRenderMock.mockResolvedValue(makeRender({ page_number: 1 }));

    render(
      <SourceVerificationPanel
        documentId="doc-1"
        documentName="contract.pdf"
        pageCount={3}
        request={request({ pageNumber: 1 })}
      />,
    );

    await waitFor(() =>
      expect(screen.getByAltText("Page 1")).toBeInTheDocument(),
    );
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();
    expect(screen.getByText("Source Verification")).toBeInTheDocument();
    expect(getPageRenderMock).toHaveBeenCalledWith("doc-1", 1, {
      highlight: "Contract Number: W912DR-26-C-0042",
      anchor: null,
      region: null,
    });
  });

  it("navigates to the correct page automatically when a different result is selected", async () => {
    getPageRenderMock.mockImplementation((_id: string, page: number) =>
      Promise.resolve(makeRender({ page_number: page })),
    );

    const { rerender } = render(
      <SourceVerificationPanel
        documentId="doc-1"
        documentName="contract.pdf"
        pageCount={10}
        request={request({ pageNumber: 1 })}
      />,
    );

    await waitFor(() =>
      expect(screen.getByText(/Page 1 of 10/)).toBeInTheDocument(),
    );

    rerender(
      <SourceVerificationPanel
        documentId="doc-1"
        documentName="contract.pdf"
        pageCount={10}
        request={request({ id: "vendor_name", pageNumber: 7, highlightText: "Vendor Name: Acme" })}
      />,
    );

    await waitFor(() =>
      expect(screen.getByText(/Page 7 of 10/)).toBeInTheDocument(),
    );
    // Page 8 may also have been prefetched in the background — assert the
    // page-7 fetch happened, not that it was necessarily the last call.
    expect(getPageRenderMock).toHaveBeenCalledWith("doc-1", 7, {
      highlight: "Vendor Name: Acme",
      anchor: null,
      region: null,
    });
  });

  it("shows a graceful error for an invalid/out-of-range page instead of crashing", async () => {
    getPageRenderMock.mockRejectedValue(new Error("Page 99 is out of range for this document."));

    render(
      <SourceVerificationPanel
        documentId="doc-1"
        documentName="contract.pdf"
        pageCount={3}
        request={request({ pageNumber: 99 })}
      />,
    );

    await waitFor(() =>
      expect(screen.getByText("Page 99 is out of range for this document.")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows a graceful error when the original PDF is unavailable", async () => {
    getPageRenderMock.mockRejectedValue(
      new Error(
        "The original file for this document is no longer available. Please re-upload.",
      ),
    );

    render(
      <SourceVerificationPanel
        documentId="doc-1"
        documentName="contract.pdf"
        pageCount={1}
        request={request()}
      />,
    );

    await waitFor(() =>
      expect(screen.getByText(/no longer available/i)).toBeInTheDocument(),
    );
  });

  it("passes a staging cell's anchor and region so the cell itself is highlighted", async () => {
    getPageRenderMock.mockResolvedValue(makeRender({ page_number: 3 }));

    render(
      <SourceVerificationPanel
        documentId="doc-1"
        documentName="Contract.pdf"
        pageCount={10}
        request={request({
          id: "clins:clin:2:contract.clin.max_amount",
          pageNumber: 3,
          highlightText: "0.00",
          anchorText: "10301",
          region: [20, 400, 580, 412],
        })}
      />,
    );

    await waitFor(() =>
      expect(getPageRenderMock).toHaveBeenCalledWith("doc-1", 3, {
        highlight: "0.00",
        anchor: "10301",
        region: [20, 400, 580, 412],
      }),
    );
  });
});
