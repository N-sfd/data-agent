import { describe, expect, it } from "vitest";

import { buildFieldRows, classifyRowKind } from "@/components/extraction/field-row";
import type { ScalarTargetResult, TargetCorrection, TargetType } from "@/types/document";

function scalar(overrides: Partial<ScalarTargetResult> = {}): ScalarTargetResult {
  return {
    target: "contract_number",
    normalized_key: "contract_number",
    value: "W912DR-26-C-0042",
    page: 1,
    confidence: 0.9,
    confidence_band: "high",
    verified: true,
    extraction_method: "source_evidence",
    display_method: "",
    evidence: {
      page_number: 1,
      source_text: "Contract Number: W912DR-26-C-0042",
      source_reference: "Page 1",
    },
    ...overrides,
  };
}

describe("buildFieldRows", () => {
  it("marks a fully resolved, verified, high-confidence scalar as extracted", () => {
    const [row] = buildFieldRows([scalar()], [], new Map());
    expect(row.status).toBe("extracted");
    expect(row.value).toBe("W912DR-26-C-0042");
  });

  it("marks an empty value as empty, not extracted", () => {
    const [row] = buildFieldRows([scalar({ value: "" })], [], new Map());
    expect(row.status).toBe("empty");
  });

  it("marks an unverified value as validation_failed", () => {
    const [row] = buildFieldRows([scalar({ verified: false })], [], new Map());
    expect(row.status).toBe("validation_failed");
  });

  it("marks a low-confidence-band value as low_confidence", () => {
    const [row] = buildFieldRows(
      [scalar({ confidence_band: "low", confidence: 0.4 })],
      [],
      new Map(),
    );
    expect(row.status).toBe("low_confidence");
  });

  it("builds a not_found row for each unresolved target", () => {
    const rows = buildFieldRows(
      [],
      [{ key: "renewal_option_date", label: "Renewal Option Date" }],
      new Map(),
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe("not_found");
    expect(rows[0].label).toBe("Renewal Option Date");
  });

  it("attaches the latest correction to its matching row", () => {
    const correction: TargetCorrection = {
      id: 1,
      document_id: "doc-1",
      normalized_key: "contract_number",
      action: "edit",
      original_value: "W912DR-26-C-0042",
      corrected_value: "W912DR-26-C-0043",
      evidence_snapshot: null,
      changed_by: null,
      created_at: new Date().toISOString(),
    };
    const [row] = buildFieldRows(
      [scalar()],
      [],
      new Map([["contract_number", correction]]),
    );
    expect(row.correction?.corrected_value).toBe("W912DR-26-C-0043");
  });

  it("handles 100+ selected fields without dropping any row", () => {
    const scalars = Array.from({ length: 80 }, (_, i) =>
      scalar({ target: `field_${i}`, normalized_key: `field_${i}` }),
    );
    const missing = Array.from({ length: 30 }, (_, i) => ({
      key: `missing_${i}`,
      label: `Missing ${i}`,
    }));
    const rows = buildFieldRows(scalars, missing, new Map());
    expect(rows).toHaveLength(110);
    expect(rows.filter((r) => r.status === "not_found")).toHaveLength(30);
  });
});

describe("classifyRowKind", () => {
  const typeByLabel = new Map<string, TargetType>([
    ["primary_contact", "contact"],
    ["cage_code", "identifier"],
  ]);

  it("uses the schema target_type when available", () => {
    const [row] = buildFieldRows(
      [scalar({ target: "primary_contact", normalized_key: "primary_contact" })],
      [],
      new Map(),
    );
    expect(classifyRowKind(row, typeByLabel)).toBe("contact");
  });

  it("falls back to a label heuristic for identifiers", () => {
    const [row] = buildFieldRows(
      [scalar({ target: "solicitation_number", normalized_key: "solicitation_number" })],
      [],
      new Map(),
    );
    expect(classifyRowKind(row, new Map())).toBe("identifier");
  });

  it("defaults to field when nothing matches", () => {
    const [row] = buildFieldRows(
      [scalar({ target: "total_value", normalized_key: "total_value" })],
      [],
      new Map(),
    );
    expect(classifyRowKind(row, new Map())).toBe("field");
  });
});
