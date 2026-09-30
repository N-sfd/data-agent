import type { StagingDataset, StagingWorkbook } from "@/lib/staging-workbook";

export interface ContractTab {
  id: string;
  label: string;
  datasetIds: string[];
}

const CONTRACT_TAB_DEFS: ContractTab[] = [
  { id: "clins", label: "CLINs", datasetIds: ["clins"] },
  { id: "clauses", label: "Clauses", datasetIds: ["clauses"] },
  { id: "far_dfars", label: "FAR / DFARS", datasetIds: ["far_references", "dfars"] },
  {
    id: "financial",
    label: "Financial & Performance",
    datasetIds: ["funding", "performance_delivery"],
  },
  { id: "other", label: "Other Contract Data", datasetIds: ["attachments"] },
  { id: "all_fields", label: "All Fields", datasetIds: ["all_fields"] },
  { id: "summary", label: "Summary", datasetIds: ["contract_summary"] },
];

function recordCount(dataset: StagingDataset | undefined): number {
  if (!dataset) return 0;
  if (dataset.cardinality === "single") {
    return dataset.records.some((record) =>
      Object.values(record.cells).some((cell) => cell.value != null),
    )
      ? 1
      : 0;
  }
  return dataset.records.length;
}

/** Contract staging tabs, empty groups omitted, Summary always last. */
export function contractTabs(datasets: StagingDataset[]): ContractTab[] {
  const byId = new Map(datasets.map((dataset) => [dataset.dataset_id, dataset]));
  return CONTRACT_TAB_DEFS.filter((tab) => {
    if (tab.id === "summary" || tab.id === "all_fields" || tab.id === "clins") return true;
    return tab.datasetIds.some((id) => recordCount(byId.get(id)) > 0);
  }).map((tab) => ({
    ...tab,
    datasetIds: tab.datasetIds.filter((id) => byId.has(id)),
  })).filter((tab) => tab.datasetIds.length > 0);
}

export function initialContractTab(workbook: StagingWorkbook): string {
  const tabs = contractTabs(workbook.datasets);
  const withRows = tabs.find((tab) => tab.id !== "summary" && tab.id !== "all_fields");
  return (withRows ?? tabs[0])?.id ?? "summary";
}

export function isContractProfile(workbook: StagingWorkbook): boolean {
  if (workbook.profile.profile_id !== "contract_v3") return false;
  return workbook.datasets.some((dataset) =>
    CONTRACT_TAB_DEFS.some((tab) => tab.datasetIds.includes(dataset.dataset_id)),
  );
}
