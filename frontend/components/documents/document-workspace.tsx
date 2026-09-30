"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronDown } from "lucide-react";

import SourceTranscription from "@/components/staging/source-transcription";
import StagingDatasetTable from "@/components/staging/staging-dataset-table";
import StagingFieldList from "@/components/staging/staging-field-list";
import { getDocument } from "@/lib/documents";
import {
  downloadExport,
  getStagingWorkbook,
  type StagingDataset,
  type StagingWorkbook,
} from "@/lib/staging-workbook";

const VIEWS = [
  { id: "overview", label: "Overview" },
  { id: "source", label: "Source" },
  { id: "staging", label: "Staging" },
  { id: "canonical", label: "Canonical" },
  { id: "transform", label: "Transform" },
  { id: "qa", label: "QA" },
] as const;

type ViewId = (typeof VIEWS)[number]["id"];

function laneOf(dataset: StagingDataset): ViewId | "advanced" {
  const id = dataset.dataset_id;
  if (dataset.role === "qa" || id.includes("qa")) return "qa";
  if (id.includes("canonical")) return "canonical";
  if (id === "far_business" || id.includes("oracle") || id.includes("map")) return "transform";
  if (id === "all_fields") return "advanced";
  if (dataset.role === "source" || id.includes("source") || id.includes("transcript")) {
    return "source";
  }
  return "staging";
}

export default function DocumentWorkspace({ documentId }: { documentId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") as ViewId | null) ?? "overview";
  const [workbook, setWorkbook] = useState<StagingWorkbook | null>(null);
  const [filename, setFilename] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [activeDataset, setActiveDataset] = useState("");
  const [farQuery, setFarQuery] = useState("");
  const [farKind, setFarKind] = useState("all");

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([getDocument(documentId), getStagingWorkbook(documentId)])
      .then(([document, staging]) => {
        if (!active) return;
        setFilename(document.original_filename || staging.document_filename);
        setWorkbook(staging);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to open this document.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [documentId]);

  const datasets = workbook?.datasets ?? [];
  const laneDatasets = useMemo(
    () => datasets.filter((dataset) => laneOf(dataset) === view),
    [datasets, view],
  );
  const advanced = datasets.filter((dataset) => laneOf(dataset) === "advanced");

  useEffect(() => {
    if (laneDatasets.length === 0) return;
    if (!laneDatasets.some((dataset) => dataset.dataset_id === activeDataset)) {
      setActiveDataset(laneDatasets[0].dataset_id);
    }
  }, [laneDatasets, activeDataset]);

  function openView(next: ViewId) {
    router.replace(`/documents/${documentId}?view=${next}`);
  }

  if (loading) {
    return <p className="px-6 py-10 text-sm text-text-secondary">Opening document workspace...</p>;
  }
  if (error || !workbook) {
    return <p className="px-6 py-10 text-sm text-danger">{error || "Unable to open this document."}</p>;
  }

  const profile = workbook.profile;
  const outcome = workbook.outcome;
  const qa = workbook.qa_summary;
  const current = laneDatasets.find((dataset) => dataset.dataset_id === activeDataset) ?? laneDatasets[0];
  const clauses = datasets.find((dataset) => dataset.dataset_id === "far_clauses");
  const alternates = datasets.find((dataset) => dataset.dataset_id === "far_alternates");
  const ready = outcome.status === "populated" || outcome.status === "special_source";
  const verified = qa.needs_review === 0 && qa.record_count > 0;
  const oracle = profile.oracle_mapping_capability;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
      <Link href="/documents" className="text-sm text-text-secondary hover:text-foreground">
        ← Documents
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{filename || workbook.document_filename}</h1>
          <p className="mt-1 text-sm text-foreground">{profile.display_name}</p>
          <p className="font-mono text-xs text-text-muted">
            {profile.profile_id}@{profile.profile_version}
          </p>
          <p className="mt-2 text-sm text-text-secondary">
            {ready ? "✓ Processing complete" : outcome.title}{" "}
            <span className="text-text-muted">
              · {outcome.record_count.toLocaleString()} source records
              {alternates ? ` · ${alternates.records.length.toLocaleString()} alternates` : ""}
              {" · "}
              {qa.needs_review.toLocaleString()} need review
            </span>
          </p>
        </div>
        <div className="relative">
          <button
            type="button"
            onClick={() => setExportOpen((open) => !open)}
            className="btn-secondary text-sm"
          >
            Export
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
          {exportOpen && (
            <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-border bg-surface py-1 shadow-sm">
              {profile.export_capabilities.map((capability) => (
                <button
                  key={capability.capability_id}
                  type="button"
                  className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-soft"
                  onClick={() => {
                    setExportOpen(false);
                    void downloadExport(capability, filename || "export");
                  }}
                >
                  {capability.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-1 border-b border-border">
        {VIEWS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => openView(item.id)}
            className={[
              "px-3 py-2 text-sm",
              view === item.id
                ? "border-b-2 border-primary font-medium text-foreground"
                : "text-text-secondary",
            ].join(" ")}
          >
            {item.label}
          </button>
        ))}
        {advanced.length > 0 && (
          <details className="ml-auto">
            <summary className="cursor-pointer list-none px-3 py-2 text-sm text-text-secondary">
              More
            </summary>
            <div className="absolute z-10 rounded-lg border border-border bg-surface py-1 shadow-sm">
              {advanced.map((dataset) => (
                <button
                  key={dataset.dataset_id}
                  type="button"
                  className="block w-full px-3 py-1.5 text-left text-sm hover:bg-surface-soft"
                  onClick={() => {
                    openView("source");
                    setActiveDataset(dataset.dataset_id);
                  }}
                >
                  {dataset.display_name}
                </button>
              ))}
            </div>
          </details>
        )}
      </div>

      <div className="mt-5">
        {view === "overview" && (
          <Overview
            workbook={workbook}
            clauses={clauses}
            alternates={alternates}
            verified={verified}
            oracle={oracle}
          />
        )}
        {view === "source" && (
          <div className="space-y-4">
            <SourceTranscription documentId={documentId} documentName={filename} />
            {current && laneOf(current) === "source" && (
              <DatasetBody documentId={documentId} dataset={current} />
            )}
          </div>
        )}
        {view === "staging" && (
          <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
            {profile.profile_id === "far_part_52" && clauses ? (
              <FarNavigator
                dataset={clauses}
                query={farQuery}
                kind={farKind}
                onQuery={setFarQuery}
                onKind={setFarKind}
                onSelect={() => setActiveDataset("far_clauses")}
              />
            ) : (
              <DatasetNav datasets={laneDatasets} active={current?.dataset_id ?? ""} onSelect={setActiveDataset} />
            )}
            <div>
              {profile.profile_id === "far_part_52" && (
                <DatasetNav datasets={laneDatasets} active={current?.dataset_id ?? ""} onSelect={setActiveDataset} />
              )}
              {current && (
                <DatasetBody
                  documentId={documentId}
                  dataset={filterFar(current, farQuery, farKind)}
                />
              )}
            </div>
          </div>
        )}
        {(view === "canonical" || view === "transform" || view === "qa") && (
          <div className="space-y-4">
            {view === "transform" && (
              <p className="text-sm text-text-secondary">
                Source → {profile.display_name} canonical → destination adapter.{" "}
                {oracle === "none"
                  ? "No destination adapter is configured."
                  : oracle === "planned"
                    ? "Adapter mapping is partially configured. This is not a final import file."
                    : "Adapter mapping is available."}
              </p>
            )}
            <DatasetNav datasets={laneDatasets} active={current?.dataset_id ?? ""} onSelect={setActiveDataset} />
            {current ? (
              <DatasetBody documentId={documentId} dataset={current} />
            ) : (
              <p className="text-sm text-text-secondary">This profile has no records in this stage yet.</p>
            )}
          </div>
        )}
      </div>

      <ol className="mt-8 flex flex-wrap gap-6 border-t border-border pt-4 text-xs text-text-secondary">
        <Readiness label="Extracted" ok={outcome.record_count > 0} />
        <Readiness label="Verified" ok={verified} />
        <Readiness label="Canonical" ok={datasets.some((dataset) => laneOf(dataset) === "canonical")} />
        <Readiness
          label="Downstream"
          ok={oracle === "available"}
          note={oracle === "planned" ? "Adapter template still required" : undefined}
        />
      </ol>
    </div>
  );
}

function Overview({
  workbook,
  clauses,
  alternates,
  verified,
  oracle,
}: {
  workbook: StagingWorkbook;
  clauses?: StagingDataset;
  alternates?: StagingDataset;
  verified: boolean;
  oracle: StagingWorkbook["profile"]["oracle_mapping_capability"];
}) {
  const qa = workbook.qa_summary;
  const quality = qa.record_count === 0 ? 0 : Math.round((qa.verified / qa.record_count) * 100);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-8">
        <Stat label="Source records" value={workbook.outcome.record_count} />
        <Stat label="Clauses" value={clauses?.records.length ?? qa.record_count} />
        <Stat label="Alternates" value={alternates?.records.length ?? 0} />
        <Stat label="Need review" value={qa.needs_review} />
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-text-muted">Quality</p>
        <div className="mt-2 h-2 max-w-md overflow-hidden rounded-full bg-surface-soft">
          <div className="h-full bg-success" style={{ width: `${quality}%` }} />
        </div>
        <p className="mt-2 text-sm text-text-secondary">
          {qa.needs_review === 0 ? "No validation issues detected." : `${qa.needs_review} items need review.`}
          {verified ? " Verification is complete." : ""}
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-text-muted">Transformation readiness</p>
        <p className="mt-2 text-sm text-foreground">
          Destination adapter{" "}
          <span className="text-text-secondary">
            {oracle === "available" ? "configured" : oracle === "planned" ? "partially configured" : "not configured"}
          </span>
        </p>
      </div>
    </div>
  );
}

function DatasetNav({
  datasets,
  active,
  onSelect,
}: {
  datasets: StagingDataset[];
  active: string;
  onSelect: (id: string) => void;
}) {
  if (datasets.length <= 1) return null;
  return (
    <div className="mb-3 flex flex-wrap gap-1.5">
      {datasets.map((dataset) => (
        <button
          key={dataset.dataset_id}
          type="button"
          onClick={() => onSelect(dataset.dataset_id)}
          className={[
            "rounded-full px-3 py-1 text-xs",
            active === dataset.dataset_id
              ? "bg-primary text-white"
              : "border border-border text-text-secondary",
          ].join(" ")}
        >
          {dataset.display_name}
        </button>
      ))}
    </div>
  );
}

function DatasetBody({ documentId, dataset }: { documentId: string; dataset: StagingDataset }) {
  if (dataset.cardinality === "single") {
    return <StagingFieldList dataset={dataset} />;
  }
  return <StagingDatasetTable documentId={documentId} dataset={dataset} />;
}

function FarNavigator({
  dataset,
  query,
  kind,
  onQuery,
  onKind,
  onSelect,
}: {
  dataset: StagingDataset;
  query: string;
  kind: string;
  onQuery: (value: string) => void;
  onKind: (value: string) => void;
  onSelect: () => void;
}) {
  const groups = new Map<string, string[]>();
  for (const record of dataset.records.slice(0, 400)) {
    const number = String(Object.values(record.cells).find((cell) => cell.canonical_field.endsWith("far_number"))?.value ?? "");
    const title = String(Object.values(record.cells).find((cell) => cell.canonical_field.endsWith("title"))?.value ?? "");
    const subpart = number.match(/^(52\.\d)/)?.[1] ?? "Other";
    const label = `Subpart ${subpart}`;
    const rows = groups.get(label) ?? [];
    if (rows.length < 8) rows.push(`${number}  ${title}`.trim());
    groups.set(label, rows);
  }
  return (
    <aside className="max-h-[70vh] overflow-auto rounded-xl border border-border bg-surface p-3">
      <p className="text-sm font-medium">FAR Part 52</p>
      <input
        value={query}
        onChange={(event) => {
          onSelect();
          onQuery(event.target.value);
        }}
        placeholder="Search FAR number, title..."
        className="mt-2 w-full rounded-lg border border-border px-2 py-1.5 text-xs outline-none"
      />
      <div className="mt-2 flex flex-wrap gap-1">
        {["all", "clause", "provision", "alternate"].map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => onKind(item)}
            className={`rounded-full px-2 py-0.5 text-[11px] ${kind === item ? "bg-primary text-white" : "border border-border"}`}
          >
            {item}
          </button>
        ))}
      </div>
      <div className="mt-3 space-y-3 text-xs">
        {[...groups.entries()].slice(0, 12).map(([label, rows]) => (
          <div key={label}>
            <p className="font-medium text-foreground">{label}</p>
            <ul className="mt-1 space-y-1 text-text-secondary">
              {rows.map((row) => (
                <li key={row}>{row}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </aside>
  );
}

function filterFar(dataset: StagingDataset, query: string, kind: string): StagingDataset {
  if (dataset.dataset_id !== "far_clauses" || (!query && kind === "all")) return dataset;
  const needle = query.trim().toLowerCase();
  const records = dataset.records.filter((record) => {
    const hay = Object.values(record.cells)
      .map((cell) => String(cell.value ?? ""))
      .join(" ")
      .toLowerCase();
    if (needle && !hay.includes(needle)) return false;
    if (kind !== "all" && !hay.includes(kind)) return false;
    return true;
  });
  return { ...dataset, records };
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-2xl font-semibold tabular-nums text-foreground">{value.toLocaleString()}</p>
      <p className="text-xs text-text-muted">{label}</p>
    </div>
  );
}

function Readiness({ label, ok, note }: { label: string; ok: boolean; note?: string }) {
  return (
    <li>
      <span className={ok ? "text-success" : "text-warning"}>{ok ? "✓" : "!"}</span> {label}
      {note && <span className="mt-0.5 block text-text-muted">{note}</span>}
    </li>
  );
}
