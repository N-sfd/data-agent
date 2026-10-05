"use client";

import { Download } from "lucide-react";
import { useEffect, useState } from "react";

import {
  downloadExport,
  getStagingProfile,
  type ExportCapability,
} from "@/lib/staging-workbook";
import type { MetadataField } from "@/types/document";

interface ExportMenuProps {
  documentId: string;
  filename: string;
  /** Kept for callers; exports no longer depend on these fields. */
  fields?: MetadataField[];
}

const FORMATS: { format: ExportCapability["format"]; label: string }[] = [
  { format: "csv", label: "CSV" },
  { format: "xlsx", label: "Excel (.xlsx)" },
  { format: "json", label: "JSON" },
];

/** Every export is the document's Professional Staging Workbook — the
 * values shown there, in its profile's own formats — never a separate
 * extraction result. */
export default function ExportMenu({ documentId, filename }: ExportMenuProps) {
  const [capabilities, setCapabilities] = useState<ExportCapability[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getStagingProfile(documentId)
      .then((profile) => {
        if (active) setCapabilities(profile.export_capabilities);
      })
      .catch(() => {
        if (active) setCapabilities([]);
      });
    return () => {
      active = false;
    };
  }, [documentId]);

  async function run(capability: ExportCapability) {
    setError("");
    try {
      await downloadExport(capability, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500">
        <Download className="h-3.5 w-3.5" />
        Export
      </span>
      {FORMATS.map(({ format, label }) => {
        const capability = capabilities.find((item) => item.format === format);
        return (
          <button
            key={format}
            type="button"
            onClick={() => capability && void run(capability)}
            disabled={!capability}
            title={capability?.label}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {label}
          </button>
        );
      })}
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
