import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import TargetPicker from "@/components/extraction/target-picker";

function renderEmpty(documentHref?: string) {
  render(
    <TargetPicker
      targets={[]}
      customQuickPicks={[]}
      selectedIds={new Set()}
      onToggle={vi.fn()}
      onToggleGroup={vi.fn()}
      onSelectAll={vi.fn()}
      onSelectAllVisible={vi.fn()}
      onClear={vi.fn()}
      onSelectCustom={vi.fn()}
      documentHref={documentHref}
    />,
  );
}

describe("TargetPicker with nothing to pick", () => {
  it("explains a running-text document and links to its text", () => {
    renderEmpty("/documents/d1?view=data");
    expect(screen.getByText(/mostly running text/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open document text/ })).toHaveAttribute("href", "/documents/d1?view=data");
  });

  it("offers no link without a document", () => {
    renderEmpty();
    expect(screen.queryByRole("link", { name: /Open document text/ })).toBeNull();
  });
});
