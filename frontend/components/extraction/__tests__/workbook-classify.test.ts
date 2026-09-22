import { describe, expect, it } from "vitest";

import type { FieldRow } from "@/components/extraction/field-row";
import {
  isBusinessFieldRow,
  isNarrativeOrSectionRow,
} from "@/components/extraction/workbook-classify";

function row(partial: Partial<FieldRow> & Pick<FieldRow, "id" | "label">): FieldRow {
  return {
    status: "extracted",
    value: null,
    confidence: 0.99,
    confidence_band: "high",
    extraction_method: "label_value",
    display_method: "Label / Value",
    evidence: null,
    verified: true,
    correction: null,
    scalar: null,
    ...partial,
  };
}

describe("workbook-classify", () => {
  it("keeps short form labels as business fields with separate values", () => {
    const name = row({
      id: "kv_10a_name",
      label: "10A. NAME",
      value: "Gabrina Daniels",
    });
    expect(isBusinessFieldRow(name)).toBe(true);
    expect(isNarrativeOrSectionRow(name)).toBe(false);
  });

  it("classifies SOW narrative kv_* as sections, not All Fields", () => {
    const general = row({
      id: "kv_b_1_general",
      label: "B.1 General",
      value: "This section describes the general requirements for the effort and related clauses. ".repeat(
        3,
      ),
    });
    expect(isNarrativeOrSectionRow(general)).toBe(true);
    expect(isBusinessFieldRow(general)).toBe(false);
  });
});
