import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AIEnrichmentNotice } from "@/components/extraction/target-results";
import type { AIEnrichmentSummary } from "@/types/document";

const base: AIEnrichmentSummary = {
  deterministic_status: "completed",
  ai_enrichment_status: "unavailable",
  reason: "AI usage limit reached.",
  notice: {
    title: "AI enhancement skipped. Deterministic extraction completed successfully.",
    detail: "AI usage limit reached.",
  },
  provider: "gemini",
  model: "gemini-3.6-flash",
  error_kind: "quota",
  error_detail: "429 RESOURCE_EXHAUSTED {'error': {'code': 429}}",
  calls_attempted: 1,
  calls_succeeded: 0,
};

describe("AIEnrichmentNotice", () => {
  it("shows a short non-blocking note, never the provider exception", () => {
    render(<AIEnrichmentNotice summary={base} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "AI enhancement skipped. Deterministic extraction completed successfully.",
    );
    expect(screen.getByText("AI usage limit reached.")).toBeInTheDocument();
    expect(screen.queryByText(/RESOURCE_EXHAUSTED/)).toBeNull();
  });

  it("renders nothing when AI was not needed or not configured", () => {
    const { container } = render(
      <AIEnrichmentNotice summary={{ ...base, ai_enrichment_status: "not_needed", notice: null }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
