import type { StagingColumn, StagingDataset, StagingWorkbook } from "@/lib/staging-workbook";

/** Presentation only. Canonical datasets stay as extracted. A group appears
 * when that document actually contains source-supported values for it. */

export interface PresentationGroup {
  id: string;
  label: string;
  datasets: StagingDataset[];
  role: "summary" | "business" | "repeating" | "other";
}

export interface PresentationManifest {
  heading: string;
  subtitle: string | null;
  family: string | null;
  groups: PresentationGroup[];
  source: true;
  reasons: string[];
}

const HIDDEN_DATASETS = new Set(["qa_review", "far_sections", "far_canonical"]);

const TECHNICAL_KEY = /found_by|extraction_method|source_page|bbox|dom_path|qa_status|value_type/i;
const TECHNICAL_LABEL = /^(type|found by|location|evidence|extraction method|confidence|status)$/i;

const SHIPPING = /incoterm|country of origin|gross weight|packages|ship via|insurance|reason for export/i;

function hasValue(dataset: StagingDataset): boolean {
  return dataset.records.some((record) =>
    Object.values(record.cells).some((cell) => cell.value != null && String(cell.value).trim() !== ""),
  );
}

function textOf(dataset: StagingDataset, suffix: string): string {
  for (const record of dataset.records) {
    for (const [key, cell] of Object.entries(record.cells)) {
      if (key.endsWith(`.${suffix}`) && cell.value != null && String(cell.value).trim()) {
        return String(cell.value).trim();
      }
    }
  }
  return "";
}

export function businessColumns(dataset: StagingDataset): StagingColumn[] {
  const columns = dataset.grid_fields?.length
    ? dataset.grid_fields
        .map((field) => dataset.columns.find((column) => column.canonical_field === field))
        .filter((column): column is StagingColumn => Boolean(column))
    : dataset.columns;
  return columns.filter(
    (column) => !TECHNICAL_KEY.test(column.key) && !TECHNICAL_LABEL.test(column.display_label.trim()),
  );
}

function presentDataset(dataset: StagingDataset): StagingDataset {
  const columns = businessColumns(dataset);
  if (columns.length === dataset.columns.length) return dataset;
  return { ...dataset, columns, grid_fields: columns.map((column) => column.canonical_field) };
}

function groupFor(dataset: StagingDataset): { id: string; label: string; role: PresentationGroup["role"] } | null {
  const id = dataset.dataset_id;
  if (dataset.role === "qa" || HIDDEN_DATASETS.has(id)) return null;
  if (!hasValue(dataset)) return null;
  if (dataset.role === "source") {
    return { id: "other", label: "Other Information", role: "other" };
  }
  if (id === "all_fields" || id === "other_fields" || id === "key_fields" || id === "other_tables") {
    const blob = dataset.records
      .map((record) => Object.values(record.cells).map((cell) => `${cell.display_label} ${cell.value ?? ""}`).join(" "))
      .join("\n");
    if (id !== "all_fields" && SHIPPING.test(blob)) {
      return { id: "shipping", label: "Shipping & Commercial", role: "business" };
    }
    return { id: "other", label: "Other Information", role: "other" };
  }
  if (/summary|overview|student_program|award/.test(id)) {
    return { id: "details", label: dataset.display_name, role: "summary" };
  }
  if (/supplier|customer|contact|party|offeror/.test(id)) {
    return { id: "parties", label: "Parties", role: "business" };
  }
  if (/line|clin|academic_record|subject/.test(id)) {
    return { id: id, label: professionalLabel(dataset.display_name), role: "repeating" };
  }
  if (/tax|charge|total|funding/.test(id)) {
    return { id: "charges", label: /total/.test(id) && !/tax|charge/.test(id) ? dataset.display_name : "Charges & Totals", role: "business" };
  }
  if (/clause|alternate|reference|business|oracle/.test(id)) {
    return { id, label: professionalLabel(dataset.display_name), role: "business" };
  }
  return { id, label: professionalLabel(dataset.display_name), role: dataset.cardinality === "repeating" ? "repeating" : "business" };
}

function professionalLabel(label: string): string {
  if (/invoice lines/i.test(label)) return "Line Items";
  if (/^all fields$/i.test(label)) return "Other Information";
  if (/^key fields$/i.test(label)) return "Other Information";
  if (/^tables?$/i.test(label) || /other tables/i.test(label)) return "Related Records";
  if (/oracle output map/i.test(label)) return "Oracle Mapping";
  if (/business export/i.test(label)) return "Clause Text";
  if (/^qa review$/i.test(label) || /source documents/i.test(label)) return "";
  return label;
}

function headingFrom(workbook: StagingWorkbook): string {
  const family = workbook.processing_metadata.document_family_label;
  const titled = workbook.datasets
    .map((dataset) => textOf(dataset, "part_heading") || textOf(dataset, "document_title") || textOf(dataset, "title"))
    .find((value) => value.length > 8 && value.length < 140);
  if (titled && !/table\s+\d|column\s+\d/i.test(titled)) return titled;
  if (family) return family;
  if (workbook.profile.display_name && !/generic/i.test(workbook.profile.display_name)) {
    return workbook.profile.display_name;
  }
  return "Structured Document";
}

export function composePresentation(workbook: StagingWorkbook): PresentationManifest {
  const buckets = new Map<string, PresentationGroup>();
  const reasons: string[] = [];
  for (const dataset of workbook.datasets) {
    const placement = groupFor(dataset);
    if (!placement || !placement.label) {
      reasons.push(`hidden:${dataset.dataset_id}`);
      continue;
    }
    const current = buckets.get(placement.id) ?? {
      id: placement.id,
      label: placement.label,
      datasets: [],
      role: placement.role,
    };
    current.datasets.push(presentDataset(dataset));
    buckets.set(placement.id, current);
    reasons.push(`group:${dataset.dataset_id}->${placement.id}`);
  }
  const groups = [...buckets.values()];
  const details = groups.filter((group) => group.role === "summary");
  const rest = groups.filter((group) => group.role !== "summary");
  const clauses = rest.some((group) => /clause/i.test(group.id));
  const ordered = clauses ? [...rest, ...details] : [...details, ...rest];
  return {
    heading: headingFrom(workbook),
    subtitle: workbook.profile.display_name,
    family: workbook.processing_metadata.document_family,
    groups: ordered,
    source: true,
    reasons,
  };
}
