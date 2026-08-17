"use client";

import { useState } from "react";
import { Braces, Check, Copy } from "lucide-react";

import type { StructuredContractOutput } from "@/types/document";

interface StructuredOutputPanelProps {
  data: StructuredContractOutput;
}

export default function StructuredOutputPanel({
  data,
}: StructuredOutputPanelProps) {
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const json = JSON.stringify(data, null, 2);

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be denied by the browser; not fatal.
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="flex items-center gap-2"
        >
          <Braces className="h-4 w-4 text-blue-600" />
          <h2 className="text-sm font-semibold text-slate-950">
            Structured Output
          </h2>
        </button>

        <button
          type="button"
          onClick={copyJson}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-600" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy JSON
            </>
          )}
        </button>
      </div>

      {expanded && (
        <pre className="mt-4 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">
          {json}
        </pre>
      )}
    </div>
  );
}
