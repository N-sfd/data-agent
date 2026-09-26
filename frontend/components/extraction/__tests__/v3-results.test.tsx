import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import V3Results from "@/components/extraction/v3-results";
import { ApiError } from "@/lib/api";
import { getNormalizedV3Document } from "@/lib/v3-export";

vi.mock("@/lib/v3-export", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/v3-export")>()),
  getNormalizedV3Document: vi.fn(),
}));

const getDoc = vi.mocked(getNormalizedV3Document);

describe("V3Results auth failures", () => {
  beforeEach(() => {
    getDoc.mockReset();
  });

  it("shows a sign-in prompt with an API keys link on 401, without retrying", async () => {
    getDoc.mockRejectedValue(new ApiError("Authentication required.", 401));

    render(<V3Results documentId="doc-1" />);

    expect(
      await screen.findByText("Sign-in required to view V3 canonical results."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "API keys" })).toHaveAttribute(
      "href",
      "/api-keys",
    );
    expect(getDoc).toHaveBeenCalledTimes(1);
  });

  it("explains insufficient permission on 403", async () => {
    getDoc.mockRejectedValue(new ApiError("Forbidden", 403));

    render(<V3Results documentId="doc-1" />);

    expect(
      await screen.findByText(
        "Your access key doesn't have permission to view V3 canonical results.",
      ),
    ).toBeInTheDocument();
    expect(getDoc).toHaveBeenCalledTimes(1);
  });
});

describe("V3Results transient failures", () => {
  beforeEach(() => {
    getDoc.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps retrying through a Render cold start (5xx/network) instead of giving up", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    getDoc
      .mockRejectedValueOnce(new ApiError("Bad Gateway", 502))
      .mockRejectedValueOnce(new Error("Cannot reach the Data Agent API"))
      .mockRejectedValueOnce(new ApiError("Service Unavailable", 503))
      .mockRejectedValueOnce(new ApiError("Service Unavailable", 503))
      .mockResolvedValue({
        document_id: "doc-1",
        document_filename: "Contract.pdf",
        contract_summary: null,
        all_fields: [],
        clins: [],
        clauses: [],
        attachments: [],
      } as unknown as Awaited<ReturnType<typeof getNormalizedV3Document>>);

    render(<V3Results documentId="doc-1" />);

    // Past the old ~12.5s give-up point, still loading rather than erroring.
    await vi.advanceTimersByTimeAsync(20_000);
    expect(screen.queryByText("Unable to load V3 canonical results.")).toBeNull();

    await vi.advanceTimersByTimeAsync(20_000);
    await vi.waitFor(() => expect(getDoc.mock.calls.length).toBeGreaterThanOrEqual(5));
    expect(screen.queryByText("Unable to load V3 canonical results.")).toBeNull();
  });

  it("fails fast on 404 without waiting out the cold-start window", async () => {
    getDoc.mockRejectedValue(new ApiError("Document not found", 404));

    render(<V3Results documentId="doc-1" />);

    expect(
      await screen.findByText("Unable to load V3 canonical results."),
    ).toBeInTheDocument();
    expect(getDoc).toHaveBeenCalledTimes(1);
  });
});

function emptyDoc(
  outcome: Awaited<ReturnType<typeof getNormalizedV3Document>>["extraction_outcome"],
) {
  return {
    document_id: "doc-1",
    document_filename: "Contract.pdf",
    all_fields: [],
    clins: [],
    funding: [],
    performance_delivery: [],
    attachments: [],
    clauses: [],
    far_references: [],
    dfars: [],
    source_documents: [
      {
        source_document: "SF1442 Award.pdf",
        role: "Embedded in Contract.pdf",
        pages: 0,
        extraction_status: "Not extracted (embedded file)",
      },
    ],
    qa_review: [],
    contract_summary: null,
    extraction_outcome: outcome,
  };
}

describe("V3Results extraction outcomes", () => {
  beforeEach(() => {
    getDoc.mockReset();
  });

  it("explains a PDF Portfolio instead of showing an empty workbook, without retrying", async () => {
    getDoc.mockResolvedValue(
      emptyDoc({
        status: "special_source",
        title: "PDF Portfolio: embedded documents need extraction",
        message: "This file is an Adobe PDF Portfolio.",
        details: ["SF1442 Award.pdf"],
        record_count: 0,
        needs_review_count: 0,
      }),
    );

    render(<V3Results documentId="doc-1" />);

    expect(
      await screen.findByText("PDF Portfolio: embedded documents need extraction"),
    ).toBeInTheDocument();
    // Opens on Source Documents, which lists the embedded file.
    expect(screen.getByText("Not extracted (embedded file)")).toBeInTheDocument();
    expect(getDoc).toHaveBeenCalledTimes(1);
  });

  it("states that no supported fields were found rather than rendering blank", async () => {
    getDoc.mockResolvedValue(
      emptyDoc({
        status: "no_supported_fields",
        title: "No supported business values identified",
        message: "The document was processed, but no fields were identified.",
        details: [],
        record_count: 0,
        needs_review_count: 0,
      }),
    );

    render(<V3Results documentId="doc-1" />);

    expect(
      await screen.findByText("No supported business values identified"),
    ).toBeInTheDocument();
    expect(getDoc).toHaveBeenCalledTimes(1);
  });

  it("does not show a banner for a fully populated result", async () => {
    getDoc.mockResolvedValue({
      ...emptyDoc({
        status: "populated",
        title: "Extraction complete",
        message: "1 source-supported record(s) staged.",
        details: [],
        record_count: 1,
        needs_review_count: 0,
      }),
      all_fields: [
        {
          category: "General",
          normalized_field: "UEID",
          value: "LLKXZRFEQMR3",
          source_file: "Contract.pdf",
          source_page: 1,
          evidence: "UEI: LLKXZRFEQMR3",
          extraction_method: "deterministic",
          qa_status: "Verified",
        },
      ],
    });

    render(<V3Results documentId="doc-1" />);

    // Opens on the first dataset that has records.
    expect(await screen.findByText("LLKXZRFEQMR3")).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
  });
});
