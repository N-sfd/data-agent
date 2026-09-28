import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PortfolioPicker, { orderPortfolioFiles } from "@/components/portfolio-picker";

// The layout that caused a 2-page cover letter to be analyzed instead of
// the 33-page award.
const FILES = [
  { filename: "response to award announcement.pdf", size_bytes: 305_000, page_count: 2 },
  { filename: "Notice of Award.pdf", size_bytes: 357_000, page_count: 3 },
  { filename: "SF1442 Award.pdf", size_bytes: 443_000, page_count: 33 },
];

describe("PortfolioPicker", () => {
  it("lists the document with the most pages first and marks it as the likely main one", () => {
    const onSelect = vi.fn();
    render(<PortfolioPicker files={FILES} onSelect={onSelect} onCancel={() => {}} />);

    const buttons = screen.getAllByRole("button").filter((b) => b.textContent?.includes(".pdf"));
    expect(buttons.map((b) => b.textContent)).toEqual([
      expect.stringContaining("SF1442 Award.pdf"),
      expect.stringContaining("Notice of Award.pdf"),
      expect.stringContaining("response to award announcement.pdf"),
    ]);
    expect(buttons[0]).toHaveTextContent("33 pages");
    expect(buttons[0]).toHaveTextContent("Largest document, likely the main one");
    expect(buttons[2]).toHaveTextContent("2 pages");
    expect(screen.getAllByText("Largest document, likely the main one")).toHaveLength(1);

    // The user still chooses; nothing is auto-selected.
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(buttons[2]);
    expect(onSelect).toHaveBeenCalledWith("response to award announcement.pdf");
  });

  it("makes no main-document claim when page counts are tied or unknown", () => {
    render(
      <PortfolioPicker
        files={[
          { filename: "a.pdf", size_bytes: 100, page_count: 3 },
          { filename: "b.pdf", size_bytes: 200, page_count: 3 },
        ]}
        onSelect={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.queryByText("Largest document, likely the main one")).toBeNull();
  });

  it("falls back to size when page counts are missing", () => {
    const ordered = orderPortfolioFiles([
      { filename: "small.pdf", size_bytes: 10 },
      { filename: "big.pdf", size_bytes: 99 },
    ]);
    expect(ordered.map((f) => f.filename)).toEqual(["big.pdf", "small.pdf"]);
  });
});
