import { describe, expect, it } from "vitest";

import {
  exportFieldsToCsvRows,
  scalarToExportField,
} from "@/lib/reviewed-export";
import type { ScalarTargetResult, TargetCorrection } from "@/types/document";

function scalar(overrides: Partial<ScalarTargetResult> = {}): ScalarTargetResult {
  return {
    target: "Total Amount",
    normalized_key: "total_amount",
    value: "$120,000",
    extracted_value: "$120,000",
    review_status: "pending",
    page: 8,
    confidence: 0.81,
    confidence_band: "medium",
    verified: true,
    extraction_method: "label_value",
    display_method: "Native",
    evidence: {
      page_number: 8,
      source_text: "Total Amount: $120,000",
      source_reference: "page 8",
    },
    validation: { status: "passed", checks: [], warnings: [] },
    ...overrides,
  };
}

describe("scalarToExportField", () => {
  it("keeps machine extract and effective value distinct after edit", () => {
    const correction: TargetCorrection = {
      id: 1,
      document_id: "doc",
      normalized_key: "total_amount",
      action: "edit",
      original_value: "$120,000",
      corrected_value: "$125,000",
      evidence_snapshot: null,
      changed_by: "reviewer",
      created_at: new Date().toISOString(),
    };
    const row = scalarToExportField(
      scalar({ extracted_value: "$120,000", value: "$120,000" }),
      correction,
    );
    expect(row.extracted_value).toBe("$120,000");
    expect(row.value).toBe("$125,000");
    expect(row.review_status).toBe("edited");
    expect(row.authoritative).toBe(true);
    expect(row.validation).toEqual({ status: "passed" });
    expect(row.source).toEqual({ page: 8 });
  });

  it("maps CSV rows with effective value as primary value column", () => {
    const rows = exportFieldsToCsvRows([
      scalarToExportField(
        scalar({
          value: "$125,000",
          extracted_value: "$120,000",
          review_status: "edited",
        }),
      ),
    ]);
    expect(rows[0].value).toBe("$125,000");
    expect(rows[0].extracted_value).toBe("$120,000");
  });
});
