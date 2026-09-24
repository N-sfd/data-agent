import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import QaBadge, {
  isNeedsReview,
  isVerifiedOrPass,
} from "@/components/extraction/v3-qa-badge";

describe("v3-qa-badge helpers", () => {
  it("recognizes Needs Review statuses case-insensitively", () => {
    expect(isNeedsReview("Needs Review")).toBe(true);
    expect(isNeedsReview("REVIEW")).toBe(true);
    expect(isNeedsReview("Verified")).toBe(false);
    expect(isNeedsReview(null)).toBe(false);
  });

  it("recognizes Verified/Pass statuses case-insensitively", () => {
    expect(isVerifiedOrPass("Verified")).toBe(true);
    expect(isVerifiedOrPass("PASS")).toBe(true);
    expect(isVerifiedOrPass("Needs Review")).toBe(false);
  });
});

describe("QaBadge", () => {
  it("renders nothing for an empty value", () => {
    const { container } = render(<QaBadge value={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the status text for a real value", () => {
    render(<QaBadge value="Needs Review" />);
    expect(screen.getByText("Needs Review")).toBeInTheDocument();
  });
});
