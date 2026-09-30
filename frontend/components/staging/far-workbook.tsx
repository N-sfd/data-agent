"use client";

import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import type { SourceViewRequest } from "@/components/source-verification-panel";
import StagingDatasetTable from "@/components/staging/staging-dataset-table";
import type { StagingCell, StagingDataset, StagingRecord, StagingWorkbook } from "@/lib/staging-workbook";

export const FAR_PROFILE_ID = "far_part_52";

export function isFarProfile(workbook: StagingWorkbook): boolean {
  return workbook.profile.profile_id === FAR_PROFILE_ID;
}

type FarTab = "clauses" | "alternates" | "references" | "transform" | "overview";
type ClauseFilter = "all" | "clause" | "provision" | "reserved" | "subpart";
type TransformView = "final" | "canonical" | "oracle" | "all_fields";

const TABS: { id: FarTab; label: string }[] = [
  { id: "clauses", label: "Clauses & Provisions" },
  { id: "alternates", label: "Alternates" },
  { id: "references", label: "FAR References" },
  { id: "transform", label: "Transform" },
  { id: "overview", label: "Overview" },
];

const FILTERS: { id: ClauseFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "clause", label: "Clause" },
  { id: "provision", label: "Provision" },
  { id: "reserved", label: "Reserved" },
  { id: "subpart", label: "Subpart / Section" },
];

function find(workbook: StagingWorkbook, id: string): StagingDataset | undefined {
  return workbook.datasets.find((dataset) => dataset.dataset_id === id);
}

function valueOf(record: StagingRecord, suffix: string): string {
  const cell = Object.entries(record.cells).find(([key]) => key.endsWith(`.${suffix}`))?.[1] as StagingCell | undefined;
  return cell?.value == null ? "" : String(cell.value);
}

function matchesQuery(record: StagingRecord, query: string): boolean {
  if (!query) return true;
  const hay = `${valueOf(record, "far_number")} ${valueOf(record, "title")} ${valueOf(record, "far_number_title")} ${valueOf(record, "title_type")}`.toLowerCase();
  return hay.includes(query);
}

export default function FarPanes({
  workbook,
  documentId,
  onOpenSource,
}: {
  workbook: StagingWorkbook;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  const [tab, setTab] = useState<FarTab>("clauses");

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="FAR sections" className="flex flex-wrap gap-1.5">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-label={label}
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={[
              "rounded-md border px-2.5 py-1 text-[13px]",
              tab === id ? "border-primary bg-primary text-white" : "border-border bg-surface text-text-secondary",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "clauses" && (
        <Clauses workbook={workbook} documentId={documentId} onOpenSource={onOpenSource} />
      )}
      {tab === "alternates" && (
        <DatasetPage
          title="Alternates"
          dataset={find(workbook, "far_alternates")}
          documentId={documentId}
          onOpenSource={onOpenSource}
        />
      )}
      {tab === "references" && (
        <DatasetPage
          title="FAR References"
          dataset={find(workbook, "far_references")}
          documentId={documentId}
          onOpenSource={onOpenSource}
        />
      )}
      {tab === "transform" && (
        <Transform workbook={workbook} documentId={documentId} onOpenSource={onOpenSource} />
      )}
      {tab === "overview" && <Overview workbook={workbook} documentId={documentId} />}
    </div>
  );
}

function DatasetPage({
  title,
  dataset,
  documentId,
  onOpenSource,
}: {
  title: string;
  dataset?: StagingDataset;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  const count = dataset?.records.length ?? 0;
  return (
    <section className="space-y-2">
      <p className="text-sm text-text-secondary">
        <span className="font-medium text-foreground">{title}</span>
        <span className="ml-2">{count.toLocaleString()} records</span>
      </p>
      {dataset && (
        <StagingDatasetTable dataset={dataset} documentId={documentId} onOpenSource={onOpenSource} dense />
      )}
    </section>
  );
}

function Clauses({
  workbook,
  documentId,
  onOpenSource,
}: {
  workbook: StagingWorkbook;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  const [filter, setFilter] = useState<ClauseFilter>("all");
  const [query, setQuery] = useState("");
  const sections = find(workbook, "far_sections");
  const clauses = find(workbook, "far_clauses");
  const source = filter === "clause" || filter === "provision" ? clauses : sections;
  const needle = query.trim().toLowerCase();
  const records = useMemo(() => {
    return (source?.records ?? []).filter((record) => {
      const type = valueOf(record, "content_type");
      const clauseType = valueOf(record, "clause_type");
      if (filter === "reserved" && type !== "RESERVED") return false;
      if (filter === "subpart" && type !== "SUBPART") return false;
      if (filter === "clause" && clauseType !== "Clause") return false;
      if (filter === "provision" && clauseType !== "Provision") return false;
      return matchesQuery(record, needle);
    });
  }, [source, filter, needle]);
  const view = source ? { ...source, records } : undefined;

  return (
    <section className="space-y-3">
      <p className="text-sm text-text-secondary">
        <span className="font-medium text-foreground">Clauses & Provisions</span>
        <span className="ml-2">{records.length.toLocaleString()} records</span>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex min-w-[220px] flex-1 items-center gap-2 rounded-lg border border-border px-2 py-1 text-sm sm:max-w-sm">
          <Search className="h-3.5 w-3.5 text-text-muted" />
          <input
            aria-label="Search FAR number or title"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search FAR number or title"
            className="w-full bg-transparent outline-none"
          />
        </label>
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setFilter(item.id)}
              className={[
                "rounded-full px-2.5 py-1 text-xs",
                filter === item.id ? "bg-primary text-white" : "border border-border text-text-secondary",
              ].join(" ")}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      {view && (
        <StagingDatasetTable key={filter} dataset={view} documentId={documentId} onOpenSource={onOpenSource} dense />
      )}
    </section>
  );
}

function Transform({
  workbook,
  documentId,
  onOpenSource,
}: {
  workbook: StagingWorkbook;
  documentId: string;
  onOpenSource?: (request: SourceViewRequest) => void;
}) {
  const [view, setView] = useState<TransformView>("final");
  const views: { id: TransformView; label: string; datasetId: string }[] = [
    { id: "final", label: "Final Output", datasetId: "far_business" },
    { id: "canonical", label: "Canonical Data", datasetId: "far_canonical" },
    { id: "oracle", label: "Oracle Mapping", datasetId: "far_oracle_output_map" },
    { id: "all_fields", label: "All Fields", datasetId: "all_fields" },
  ];
  const current = views.find((item) => item.id === view) ?? views[0];
  const dataset = find(workbook, current.datasetId);
  return (
    <section className="space-y-3">
      <div role="tablist" aria-label="Transform views" className="flex flex-wrap gap-3 border-b border-border text-sm">
        {views.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={view === item.id}
            onClick={() => setView(item.id)}
            className={[
              "-mb-px border-b-2 px-1 py-1.5",
              view === item.id ? "border-primary text-foreground" : "border-transparent text-text-secondary",
            ].join(" ")}
          >
            {item.label}
          </button>
        ))}
      </div>
      {view === "oracle" && (
        <p className="text-sm text-text-secondary">
          Oracle output mapping is an adapter specification, not a final Oracle import file.
        </p>
      )}
      {view === "final" && (
        <p className="text-sm text-text-secondary">
          {(dataset?.records.length ?? 0).toLocaleString()} records. Long description and text open from Details.
        </p>
      )}
      {dataset && (
        <StagingDatasetTable dataset={dataset} documentId={documentId} onOpenSource={onOpenSource} dense />
      )}
    </section>
  );
}

function Overview({ workbook, documentId }: { workbook: StagingWorkbook; documentId: string }) {
  const overview = find(workbook, "far_overview")?.records[0];
  const qa = find(workbook, "qa_review");
  const metric = (suffix: string) => (overview ? valueOf(overview, suffix) : "");
  const checks = qa?.records.length ?? 0;
  const failed = qa?.records.filter((record) => valueOf(record, "result").toUpperCase() !== "PASS").length ?? 0;
  const metrics = [
    ["FAR records", metric("records")],
    ["Clauses / provisions", metric("clauses_provisions")],
    ["Alternates", metric("alternates")],
    ["Embedded references", metric("with_references")],
    ["Reserved", metric("reserved")],
    ["Load eligible", metric("load_eligible")],
  ];
  return (
    <section className="space-y-6">
      <dl className="grid gap-3 sm:grid-cols-3">
        {metrics.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-border px-3 py-2">
            <dt className="text-[11px] uppercase tracking-wide text-text-muted">{label}</dt>
            <dd className="text-lg font-semibold tabular-nums">{value || "—"}</dd>
          </div>
        ))}
      </dl>
      <div>
        <h4 className="text-sm font-medium">Validation & Review</h4>
        <p className="mt-1 text-sm text-text-secondary">
          {checks} checks · {failed === 0 ? "all passed" : `${failed} need review`}
        </p>
        <details className="mt-2">
          <summary className="cursor-pointer text-sm text-primary">View validation details</summary>
          {qa && <StagingDatasetTable dataset={qa} documentId={documentId} />}
        </details>
      </div>
      <p className="text-xs text-text-secondary">
        {workbook.profile.display_name} · {workbook.profile.profile_id}@{workbook.profile.profile_version}
        {workbook.processing_metadata.resolved_at ? ` · ${workbook.processing_metadata.resolved_at}` : ""}
      </p>
    </section>
  );
}
