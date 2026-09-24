import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import V3DatasetTable from "@/components/extraction/v3-dataset-table";

const COLUMNS: [string, string][] = [
  ["clin", "CLIN"],
  ["description", "Description"],
  ["source_page", "Source Page"],
  ["evidence", "Evidence"],
  ["qa_status", "QA Status"],
];

function rows(count: number, reviewEvery = 3) {
  return Array.from({ length: count }, (_, i) => ({
    clin: `1030${i}`,
    description: `Domain item ${i}`,
    source_page: 3,
    evidence: `Evidence text for row ${i}`,
    qa_status: i % reviewEvery === 0 ? "Needs Review" : "Verified",
  }));
}

describe("V3DatasetTable", () => {
  it("shows the empty-dataset message when there are no rows at all", () => {
    render(<V3DatasetTable datasetId="clins" columns={COLUMNS} rows={[]} />);
    expect(screen.getByText("No source-supported records found.")).toBeInTheDocument();
  });

  it("renders every row when no filter is applied", () => {
    render(<V3DatasetTable datasetId="clins" columns={COLUMNS} rows={rows(5)} />);
    expect(screen.getByText("5 of 5 records")).toBeInTheDocument();
  });

  it("filters down to only Needs Review rows", () => {
    render(<V3DatasetTable datasetId="clins" columns={COLUMNS} rows={rows(6)} />);
    fireEvent.click(screen.getByRole("button", { name: "Needs Review" }));
    // rows 0 and 3 (index % 3 === 0) are Needs Review out of 6 rows.
    expect(screen.getByText("2 of 6 records")).toBeInTheDocument();
  });

  it("paginates datasets larger than the page size", () => {
    render(
      <V3DatasetTable datasetId="clauses" columns={COLUMNS} rows={rows(60)} pageSize={25} />,
    );
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();
  });

  it("calls onOpenSource with the row's page and evidence when clicked", () => {
    const onOpenSource = vi.fn();
    render(
      <V3DatasetTable
        datasetId="clins"
        columns={COLUMNS}
        rows={rows(1)}
        identityColumns={["clin", "description"]}
        onOpenSource={onOpenSource}
      />,
    );
    fireEvent.click(screen.getByText("10300"));
    expect(onOpenSource).toHaveBeenCalledWith(
      expect.objectContaining({
        pageNumber: 3,
        label: "10300",
        value: "Domain item 0",
      }),
    );
  });
});
