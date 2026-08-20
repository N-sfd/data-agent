"use client";

import { useState } from "react";
import { Braces, Check, Copy, Download } from "lucide-react";

import type { StructuredContractOutput } from "@/types/document";

interface StructuredOutputPanelProps {
  data: StructuredContractOutput;
}

export default function StructuredOutputPanel({
  data,
}: StructuredOutputPanelProps) {
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

  function downloadJson() {
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "structured-output.json";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="editorial-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Braces className="h-4 w-4 text-primary" />
          <h2 className="text-lg font-medium text-foreground">
            Structured Output
          </h2>
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={copyJson} className="btn-secondary py-1.5 text-xs">
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-success" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                Copy JSON
              </>
            )}
          </button>
          <button type="button" onClick={downloadJson} className="btn-secondary py-1.5 text-xs">
            <Download className="h-3.5 w-3.5" />
            Download JSON
          </button>
        </div>
      </div>

      <pre className="mt-4 max-h-[32rem] overflow-auto rounded-xl border border-border bg-slate-950 p-4 text-xs leading-5 text-slate-100">
        {json}
      </pre>
    </div>
  );
}
