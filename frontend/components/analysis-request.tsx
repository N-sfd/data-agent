"use client";

import { ArrowRight, Loader2, Search } from "lucide-react";
import { useState } from "react";

import ExtractionInstruction from "@/components/extraction/extraction-instruction";
import TargetPicker, {
  type CustomQuickPick,
} from "@/components/extraction/target-picker";
import type {
  DocumentTarget,
  ExtractTargetsResult,
  TargetType,
  UniversalExtractionResult,
} from "@/types/document";

interface AnalysisRequestProps {
  disabled?: boolean;
  waking?: boolean;
  targets?: DocumentTarget[];
  documentFamilyLabel?: string | null;
  schemaDiscovering?: boolean;

  onExtractTargets: (
    targetIds: string[],
  ) => Promise<ExtractTargetsResult>;

  onAnalyze: (
    instruction: string,
  ) => Promise<UniversalExtractionResult>;
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
  targets = [],
  documentFamilyLabel = null,
  schemaDiscovering = false,
  onExtractTargets,
  onAnalyze,
}: AnalysisRequestProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState("");
  const [noMatch, setNoMatch] = useState(false);

  const [instruction, setInstruction] = useState("");
  const [instructionExpanded, setInstructionExpanded] = useState(false);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");

  const busy = disabled || extracting || asking;

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
          <div className="flex items-center gap-2 rounded-xl border border-border bg-surface-soft px-4 py-6 text-sm text-text-secondary">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            Discovering document schema...
          </div>
        ) : (
          <TargetPicker
            targets={targets}
            customQuickPicks={CUSTOM_QUICK_PICKS}
            selectedIds={selectedIds}
            disabled={busy}
            onToggle={toggleTarget}
            onSelectAll={selectAllOfType}
            onClear={clearSelection}
            onSelectCustom={selectCustomQuickPick}
          />
        )}
      </div>

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
            : "Running extraction against detected document schema..."}
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
