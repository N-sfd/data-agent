import { describe, expect, it } from "vitest";

import { composePresentation } from "@/lib/presentation-manifest";
import type { StagingCell, StagingDataset, StagingWorkbook } from "@/lib/staging-workbook";

function cell(canonical_field: string, display_label: string, value: string): StagingCell {
  return {
    canonical_field,
    display_label,
    value,
    raw_value: value,
    review_status: "Verified",
    review_reasons: [],
    provenance: null,
    validation: { status: "passed", checks: [] },
  } as unknown as StagingCell;
}

function dataset(dataset_id: string, display_name: string, columns: [string, string][], rows: Record<string, string>[]): StagingDataset {
  return {
    dataset_id,
    display_name,
    cardinality: "repeating",
    role: "business",
    description: null,
    columns: columns.map(([canonical_field, display_label]) => ({
      canonical_field,
      key: canonical_field.split(".").pop() as string,
      display_label,
      value_type: "text",
      expected: false,
    })),
    records: rows.map((row, index) => ({
      record_id: `r${index}`,
      cells: Object.fromEntries(
        Object.entries(row).map(([field, value]) => [field, cell(field, columns.find(([f]) => f === field)?.[1] ?? field, value)]),
      ),
      record_status: "Verified",
      links_to_dataset: null,
    })),
  } as unknown as StagingDataset;
}

function resume(): StagingWorkbook {
  return {
    document_id: "d1",
    document_filename: "Resume.pdf",
    profile: { profile_id: "generic_business_document", profile_version: 2, display_name: "Generic Business Document", export_capabilities: [], views: [] },
    outcome: { status: "populated" },
    processing_metadata: { document_family: "unknown" },
    qa_summary: { record_count: 3, verified: 3, needs_review: 0 },
    datasets: [
      dataset(
        "document_sections",
        "Sections",
        [
          ["document.section.heading", "Section"],
          ["document.section.content", "Content"],
        ],
        [
          { "document.section.heading": "Professional Summary", "document.section.content": "Data scientist with 5+ years." },
          { "document.section.heading": "Education", "document.section.content": "State University\nMS, Computer Science" },
        ],
      ),
      dataset(
        "all_fields",
        "All Fields",
        [
          ["document.field.category", "Category"],
          ["document.field.name", "Field"],
          ["document.field.value", "Value"],
        ],
        [{ "document.field.category": "Heading", "document.field.name": "Heading", "document.field.value": "Education" }],
      ),
    ],
  } as unknown as StagingWorkbook;
}

describe("document sections", () => {
  it("reads each heading with its text on a Content tab, never as a Heading tab", () => {
    const manifest = composePresentation(resume());
    expect(manifest.groups.map((group) => group.label)).toEqual(["Content"]);
    const sections = manifest.groups[0].sections;
    expect(sections.map((section) => [section.pattern, section.title])).toEqual([
      ["text", "Professional Summary"],
      ["text", "Education"],
    ]);
    const item = sections[1].items[0];
    expect(item.cell.value).toBe("State University\nMS, Computer Science");
    // Selectable and exportable by id, like any other value.
    expect(item.source).toEqual({ datasetId: "document_sections", recordId: "r1", field: "document.section.content" });
  });
});
