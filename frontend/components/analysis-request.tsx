"use client";

import { ArrowRight, Loader2, Save, Search } from "lucide-react";
import { useState } from "react";

import ExtractionInstruction from "@/components/extraction/extraction-instruction";
import TargetPicker, {
  type CustomQuickPick,
} from "@/components/extraction/target-picker";
import {
  addExtractionField,
  createExtractionModel,
  listExtractionModels,
} from "@/lib/extraction-models";
import type {
  DocumentTarget,
  ExtractionJob,
  ExtractionModel,
  ExtractTargetsResult,
  TargetType,
  UniversalExtractionResult,
} from "@/types/document";

const STAGE_LABELS: Record<string, string> = {
  extracting_data: "Extracting selected fields…",
  validating_results: "Validating results…",
  complete: "Finishing up…",
};

function extractionStageLabel(job: ExtractionJob | null | undefined): string {
  if (!job) return "Running extraction against detected document schema...";
  if (job.status === "queued") return "Queued…";
  if (job.stage && STAGE_LABELS[job.stage]) return STAGE_LABELS[job.stage];
  return "Running extraction against detected document schema...";
}

interface AnalysisRequestProps {
  disabled?: boolean;
  waking?: boolean;
  extractionJob?: ExtractionJob | null;
  targets?: DocumentTarget[];
  documentFamilyLabel?: string | null;
  schemaDiscovering?: boolean;
  schemaDiscoveryError?: string;
  onRetryDiscovery?: () => void;

  onExtractTargets: (
    targetIds: string[],
  ) => Promise<ExtractTargetsResult>;

  onAnalyze: (
    instruction: string,
  ) => Promise<UniversalExtractionResult>;

  onAddCustomField?: (label: string) => Promise<DocumentTarget | undefined>;
  onRenameCustomField?: (targetKey: string, label: string) => Promise<void>;
  onDeleteCustomField?: (targetKey: string) => Promise<void>;
}

const CUSTOM_QUICK_PICKS: CustomQuickPick[] = [
  {
    key: "custom_instruction",
    label: "Write a custom instruction",
    prompt: "",
  },
];

export default function AnalysisRequest({
  disabled = false,
  waking = false,
  extractionJob = null,
  targets = [],
  documentFamilyLabel = null,
  schemaDiscovering = false,
  schemaDiscoveryError = "",
  onRetryDiscovery,
  onExtractTargets,
  onAnalyze,
  onAddCustomField,
  onRenameCustomField,
  onDeleteCustomField,
}: AnalysisRequestProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState("");
  const [noMatch, setNoMatch] = useState(false);

  const [instruction, setInstruction] = useState("");
  const [instructionExpanded, setInstructionExpanded] = useState(false);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");

  const [savingSchema, setSavingSchema] = useState(false);
  const [saveSchemaName, setSaveSchemaName] = useState("");
  const [schemaActionError, setSchemaActionError] = useState("");
  const [schemaActionBusy, setSchemaActionBusy] = useState(false);
  const [savedModels, setSavedModels] = useState<ExtractionModel[] | null>(
    null,
  );
  const [loadingModels, setLoadingModels] = useState(false);

  const busy = disabled || extracting || asking;

  async function saveCurrentSelectionAsSchema() {
    if (!saveSchemaName.trim() || selectedIds.size === 0) return;

    setSchemaActionBusy(true);
    setSchemaActionError("");

    try {
      const model = await createExtractionModel(
        saveSchemaName.trim(),
        `Saved from Extraction Workspace (${selectedIds.size} fields)`,
      );

      const selectedTargets = targets.filter((target) =>
        selectedIds.has(target.id),
      );

      for (const target of selectedTargets) {
        await addExtractionField(model.id, target.label, "", "text");
      }

      setSavingSchema(false);
      setSaveSchemaName("");
    } catch (error) {
      setSchemaActionError(
        error instanceof Error ? error.message : "Couldn't save schema.",
      );
    } finally {
      setSchemaActionBusy(false);
    }
  }

  async function openLoadSchema() {
    setSchemaActionError("");
    setLoadingModels(true);

    try {
      const models = await listExtractionModels();
      setSavedModels(models);
    } catch (error) {
      setSchemaActionError(
        error instanceof Error ? error.message : "Couldn't load schemas.",
      );
    } finally {
      setLoadingModels(false);
    }
  }

  async function applySchema(model: ExtractionModel) {
    setSchemaActionBusy(true);
    setSchemaActionError("");

    try {
      const nextSelected = new Set(selectedIds);

      for (const field of model.fields) {
        const match = targets.find(
          (target) =>
            target.label.toLowerCase() === field.field_name.toLowerCase(),
        );

        if (match) {
          nextSelected.add(match.id);
          continue;
        }

        if (onAddCustomField) {
          const created = await onAddCustomField(field.field_name);
          if (created) {
            nextSelected.add(created.id);
          }
        }
      }

      setSelectedIds(nextSelected);
      setSavedModels(null);
    } catch (error) {
      setSchemaActionError(
        error instanceof Error ? error.message : "Couldn't apply schema.",
      );
    } finally {
      setSchemaActionBusy(false);
    }
  }

  function toggleTarget(targetId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(targetId)) {
        next.delete(targetId);
      } else {
        next.add(targetId);
      }
      return next;
    });
    setNoMatch(false);
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  async function runExtraction(targetIds: string[]) {
    if (targetIds.length === 0) return;

    setExtracting(true);
    setExtractError("");
    setNoMatch(false);

    try {
      const result = await onExtractTargets(targetIds);
      if (result.scalars.length === 0 && result.tables.length === 0) {
        setNoMatch(true);
      }
    } catch (error) {
      setExtractError(
        error instanceof Error ? error.message : "Extraction failed.",
      );
    } finally {
      setExtracting(false);
    }
  }

  function selectAllOfType(targetType: TargetType) {
    const ids = targets
      .filter((target) => target.target_type === targetType)
      .map((target) => target.id);

    if (ids.length === 0) return;

    setSelectedIds(new Set(ids));
    void runExtraction(ids);
  }

  function selectAllVisible(targetIds: string[]) {
    if (targetIds.length === 0) return;

    setSelectedIds(new Set(targetIds));
    void runExtraction(targetIds);
  }

  function toggleGroup(targetIds: string[]) {
    setSelectedIds((current) => {
      const allSelected = targetIds.every((id) => current.has(id));
      const next = new Set(current);
      for (const id of targetIds) {
        if (allSelected) {
          next.delete(id);
        } else {
          next.add(id);
        }
      }
      return next;
    });
    setNoMatch(false);
  }

  function selectCustomQuickPick(pick: CustomQuickPick) {
    setInstruction(pick.prompt);
    setInstructionExpanded(true);
  }

  async function askQuestion() {
    if (!instruction.trim()) return;

    setAsking(true);
    setAskError("");

    try {
      await onAnalyze(instruction.trim());
    } catch (error) {
      setAskError(
        error instanceof Error ? error.message : "Analysis failed.",
      );
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="editorial-card p-6 sm:p-8">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
          <Search className="h-5 w-5 text-primary" strokeWidth={1.75} />
        </div>

        <div className="min-w-0">
          <h2 className="text-lg font-medium text-foreground">
            Universal Extraction
          </h2>
          <p className="mt-0.5 text-base font-medium text-foreground">
            What do you want to extract?
          </p>
          <p className="mt-1 text-sm leading-6 text-text-secondary">
            Search the document schema — fields, tables, sections, and clauses
            actually detected in this file.
          </p>
        </div>
      </div>

      {documentFamilyLabel && (
        <p className="mt-4 text-xs text-text-secondary">
          Detected as{" "}
          <span className="font-medium text-foreground">
            {documentFamilyLabel}
          </span>
        </p>
      )}

      <div className="mt-5">
        {schemaDiscovering ? (
          <div className="space-y-3 rounded-xl border border-border bg-surface-soft px-4 py-5">
            <div className="flex items-center gap-2 text-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              {waking
                ? "Waking processing service…"
                : "Discovering fields, tables, and clauses in this document…"}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <div
                  key={index}
                  className="h-10 animate-pulse rounded-lg border border-border/70 bg-surface"
                />
              ))}
            </div>
            <p className="text-xs leading-5 text-text-muted">
            Only structures with source evidence appear — Detected means Data Agent
            can show where it exists in this file, not that AI thinks it might.
            </p>
          </div>
        ) : schemaDiscoveryError ? (
          <div className="space-y-3 rounded-xl border border-danger/20 bg-danger/5 p-4">
            <p className="text-sm font-medium text-danger">
              Couldn&apos;t discover this document&apos;s schema
            </p>
            <p className="text-sm leading-6 text-danger/80">
              {schemaDiscoveryError}
            </p>
            {onRetryDiscovery && (
              <button
                type="button"
                onClick={onRetryDiscovery}
                className="btn-secondary text-sm"
              >
                Retry
              </button>
            )}
          </div>
        ) : (
          <TargetPicker
            targets={targets}
            customQuickPicks={CUSTOM_QUICK_PICKS}
            selectedIds={selectedIds}
            disabled={busy}
            onToggle={toggleTarget}
            onToggleGroup={toggleGroup}
            onSelectAll={selectAllOfType}
            onSelectAllVisible={selectAllVisible}
            onClear={clearSelection}
            onSelectCustom={selectCustomQuickPick}
            onAddCustomField={onAddCustomField}
            onRenameCustomField={onRenameCustomField}
            onDeleteCustomField={onDeleteCustomField}
          />
        )}
      </div>

      {!schemaDiscovering && !schemaDiscoveryError && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={busy || selectedIds.size === 0}
            onClick={() => {
              setSavedModels(null);
              setSavingSchema((value) => !value);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-text-secondary transition hover:text-foreground disabled:opacity-40"
          >
            <Save className="h-3.5 w-3.5" />
            Save schema
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setSavingSchema(false);
              void openLoadSchema();
            }}
            className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-text-secondary transition hover:text-foreground disabled:opacity-40"
          >
            Reuse saved schema
          </button>
        </div>
      )}

      {savingSchema && (
        <div className="mt-2 flex items-center gap-2 rounded-xl border border-border bg-surface-soft p-2.5">
          <input
            type="text"
            value={saveSchemaName}
            onChange={(event) => setSaveSchemaName(event.target.value)}
            placeholder={`Name this schema (${selectedIds.size} fields)`}
            className="flex-1 bg-transparent px-1.5 text-sm text-foreground outline-none placeholder:text-text-muted"
          />
          <button
            type="button"
            disabled={schemaActionBusy || !saveSchemaName.trim()}
            onClick={() => void saveCurrentSelectionAsSchema()}
            className="btn-secondary px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-40"
          >
            {schemaActionBusy ? "Saving…" : "Save"}
          </button>
        </div>
      )}

      {savedModels !== null && (
        <div className="mt-2 rounded-xl border border-border bg-surface-soft p-2.5">
          {loadingModels ? (
            <p className="px-1.5 py-1 text-sm text-text-secondary">
              Loading saved schemas…
            </p>
          ) : savedModels.length === 0 ? (
            <p className="px-1.5 py-1 text-sm text-text-secondary">
              No saved schemas yet.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {savedModels.map((model) => (
                <li
                  key={model.id}
                  className="flex items-center justify-between gap-2 px-1.5 py-1.5"
                >
                  <span className="min-w-0 truncate text-sm text-foreground">
                    {model.name}{" "}
                    <span className="text-xs text-text-muted">
                      ({model.fields.length} fields)
                    </span>
                  </span>
                  <button
                    type="button"
                    disabled={schemaActionBusy}
                    onClick={() => void applySchema(model)}
                    className="btn-secondary px-2.5 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Apply
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {schemaActionError && (
        <p className="mt-2 text-xs text-danger">{schemaActionError}</p>
      )}

      <button
        type="button"
        disabled={busy || selectedIds.size === 0}
        onClick={() => void runExtraction(Array.from(selectedIds))}
        className="btn-primary mt-4 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {extracting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Extracting selected targets...
          </>
        ) : (
          <>
            Extract Selected{selectedIds.size ? ` (${selectedIds.size})` : ""}
            <ArrowRight className="h-4 w-4" />
          </>
        )}
      </button>

      {extracting && (
        <div className="mt-4 rounded-xl border border-primary/15 bg-primary/5 px-3.5 py-2.5 text-sm text-text-secondary">
          {waking
            ? "Waking processing service — first request after idle can take up to a minute."
            : extractionStageLabel(extractionJob)}
          {extractionJob && extractionJob.progress > 0 && (
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-primary/10">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${extractionJob.progress}%` }}
              />
            </div>
          )}
        </div>
      )}

      {noMatch && (
        <div className="mt-4 rounded-xl border border-warning/25 bg-warning/5 p-4 text-sm text-warning">
          That selection didn&apos;t resolve to any values in this document.
        </div>
      )}

      {extractError && (
        <div className="mt-4 rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">
          {extractError}
        </div>
      )}

      <div className="mt-6 border-t border-border pt-5">
        <p className="text-xs font-medium text-text-muted">
          Or ask anything not listed above
        </p>
        <div className="mt-2">
          <ExtractionInstruction
            value={instruction}
            disabled={busy}
            expanded={instructionExpanded}
            onChange={setInstruction}
            onToggleExpand={() =>
              setInstructionExpanded((value) => !value)
            }
          />
        </div>

        <button
          type="button"
          disabled={busy || !instruction.trim()}
          onClick={() => void askQuestion()}
          className="btn-secondary mt-3 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {asking ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing...
            </>
          ) : (
            "Ask / Extract Custom"
          )}
        </button>

        {asking && waking && (
          <div className="mt-3 rounded-xl border border-primary/15 bg-primary/5 px-3.5 py-2.5 text-sm text-text-secondary">
            Waking processing service — first request after idle can take up to
            a minute.
          </div>
        )}

        {askError && (
          <div className="mt-3 rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">
            {askError}
          </div>
        )}
      </div>
    </div>
  );
}
