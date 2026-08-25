"use client";

import { ArrowRight, Search } from "lucide-react";
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

  onExtractTargets: (
    targetIds: string[],
  ) => Promise<ExtractTargetsResult>;

  onAnalyze: (
    instruction: string,
  ) => Promise<UniversalExtractionResult>;
}

const CUSTOM_QUICK_PICKS: CustomQuickPick[] = [
  { key: "custom_field", label: "Custom Field", prompt: "" },
  { key: "custom_table", label: "Custom Table", prompt: "" },
  { key: "custom_question", label: "Custom Question", prompt: "" },
  {
    key: "custom_instruction",
    label: "Custom Extraction Instruction",
    prompt: "",
  },
];

export default function AnalysisRequest({
  disabled = false,
  waking = false,
  targets = [],
  documentFamilyLabel = null,
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
      if (
        result.scalars.length === 0 &&
        result.tables.length === 0
      ) {
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
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50">
          <Search className="h-5 w-5 text-blue-600" />
        </div>

        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Universal Extraction
          </h2>
          <p className="mt-0.5 text-base font-medium text-slate-800">
            What do you want to extract?
          </p>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            Search fields, tables, sections, clauses, and other
            information actually detected in this document.
          </p>
        </div>
      </div>

      {documentFamilyLabel && (
        <p className="mt-4 text-xs text-slate-500">
          Detected as{" "}
          <span className="font-medium text-slate-700">
            {documentFamilyLabel}
          </span>
        </p>
      )}

      <div className="mt-4">
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
      </div>

      <button
        type="button"
        disabled={busy || selectedIds.size === 0}
        onClick={() => void runExtraction(Array.from(selectedIds))}
        className="mt-4 inline-flex items-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {extracting
          ? "Extracting..."
          : `Extract Selected${selectedIds.size ? ` (${selectedIds.size})` : ""}`}
        {!extracting && <ArrowRight className="h-4 w-4" />}
      </button>

      {extracting && waking && (
        <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">
          Waking processing service... this can take up to a minute
          after a deploy.
        </div>
      )}

      {noMatch && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          That selection didn&apos;t resolve to any values in this
          document.
        </div>
      )}

      {extractError && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {extractError}
        </div>
      )}

      <div className="mt-6 border-t border-slate-100 pt-5">
        <p className="text-xs font-medium text-slate-500">
          Custom — ask anything
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
          className="mt-3 inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {asking ? "Analyzing..." : "Ask / Extract Custom"}
        </button>

        {askError && (
          <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {askError}
          </div>
        )}
      </div>
    </div>
  );
}
