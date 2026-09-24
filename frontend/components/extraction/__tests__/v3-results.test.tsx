import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
