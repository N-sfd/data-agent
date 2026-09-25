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
