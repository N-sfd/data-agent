import { describe, expect, it } from "vitest";

import { refineGroups, type PresentationGroup, type PresentationSection } from "@/lib/presentation-manifest";

function detail(id: string, title: string | null, count: number): PresentationSection {
  return {
    id,
    title,
    pattern: "detail",
    items: Array.from({ length: count }, (_, i) => ({ id: `${id}:${i}`, label: `Field ${i}` })),
  } as unknown as PresentationSection;
}

describe("refineGroups", () => {
  const base = (): PresentationGroup[] => [
    { id: "summary", label: "Invoice Summary", sections: [detail("main", null, 4), detail("refs", "References", 1)] },
    { id: "parties", label: "Parties", sections: [detail("p", null, 2)] },
  ];

  it("names the summary Summary, titles its card and merges a single reference", () => {
    const [summary] = refineGroups(base(), "Invoice");
    expect(summary.label).toBe("Summary");
    expect(summary.sections).toHaveLength(1);
    expect(summary.sections[0]).toMatchObject({ pattern: "card", title: "Invoice Details" });
    expect(summary.sections[0].items).toHaveLength(5);
  });

  it("folds a small Other Information into the Summary", () => {
    const groups = refineGroups([...base(), { id: "other", label: "Other Information", sections: [detail("notes", "Notes", 1)] }], "Invoice");
    expect(groups.map((group) => group.label)).toEqual(["Summary", "Parties"]);
    expect(groups[0].sections.at(-1)).toMatchObject({ title: "Additional Information" });
  });

  it("names a single-subject Other tab after its subject", () => {
    const groups = refineGroups(
      [...base(), { id: "other", label: "Other Information", sections: [detail("ship", "Shipping & Commercial", 6)] }],
      "Invoice",
    );
    expect(groups.map((group) => group.label)).toEqual(["Summary", "Parties", "Shipping & Commercial"]);
    expect(groups[2].sections[0].title).toBeNull();
  });

  it("uses Document Details for a long document title", () => {
    const [summary] = refineGroups(base(), "Part 52 - Solicitation Provisions and Contract Clauses");
    expect(summary.sections[0].title).toBe("Document Details");
  });
});
