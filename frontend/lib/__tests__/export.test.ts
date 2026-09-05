import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadCsv, downloadJson, toCsv, toTsv } from "@/lib/export";

describe("toCsv", () => {
  it("quotes values and escapes embedded quotes", () => {
    const csv = toCsv(
      ["field", "value"],
      [{ field: "Contract Number", value: 'W912DR-26-C-0042 "final"' }],
    );
    const lines = csv.split("\n");
    expect(lines[0]).toBe('"field","value"');
    expect(lines[1]).toBe('"Contract Number","W912DR-26-C-0042 ""final"""');
  });

  it("renders missing values as an empty cell, not the literal 'undefined'", () => {
    const csv = toCsv(["field", "value"], [{ field: "Renewal Date" }]);
    expect(csv).toContain('"Renewal Date",""');
  });
});

describe("toTsv", () => {
  it("joins rows with tabs in header order", () => {
    const tsv = toTsv(
      ["field", "value"],
      [{ field: "Contract Number", value: "W912DR-26-C-0042" }],
    );
    expect(tsv).toBe("field\tvalue\nContract Number\tW912DR-26-C-0042");
  });
});

describe("downloadJson / downloadCsv", () => {
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;

  afterEach(() => {
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
    vi.restoreAllMocks();
  });

  it("serializes JSON with confidence/method/source/validation preserved", () => {
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    const rows = [
      {
        field: "Contract Number",
        value: "W912DR-26-C-0042",
        confidence: 0.9,
        method: "source_evidence",
        source_page: 1,
        validation_status: "extracted",
      },
    ];

    downloadJson("fields.json", rows);
    downloadCsv(
      "fields.csv",
      ["field", "value", "confidence", "method", "source_page", "validation_status"],
      rows,
    );

    expect(clickSpy).toHaveBeenCalledTimes(2);
    expect(URL.createObjectURL).toHaveBeenCalledTimes(2);
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
  });
});
