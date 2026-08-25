"use client";

import { X } from "lucide-react";

import {
  DETECTION_TYPE_ORDER,
  DETECTION_TYPE_PLURAL,
  groupByPage,
} from "@/lib/detection";
import type { StructureDetectionResult } from "@/types/document";

interface DetectedContentDrawerProps {
  open: boolean;
  onClose: () => void;
  structureDetection: StructureDetectionResult;
}

export default function DetectedContentDrawer({
  open,
  onClose,
  structureDetection,
}: DetectedContentDrawerProps) {
  if (!open) {
    return null;
  }

  const { detected_targets: named, possible_targets: possible } =
    structureDetection;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-slate-950/30"
        onClick={onClose}
      />

      <div className="relative flex h-full w-full max-w-md flex-col overflow-y-auto bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Detected Content
            </h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {structureDetection.document_family_label}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-6 space-y-6">
          {DETECTION_TYPE_ORDER.map((type) => {
            const namedForType = named.filter(
              (target) => target.extraction_type === type,
            );
            const pageGroups = groupByPage(possible, type);

            if (namedForType.length === 0 && pageGroups.length === 0) {
              return null;
            }

            return (
              <div key={type}>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {DETECTION_TYPE_PLURAL[type]}
                </p>

                {namedForType.length > 0 && (
                  <ul className="mt-2 space-y-1.5">
                    {namedForType.map((target) => (
                      <li
                        key={target.key}
                        className="flex items-center justify-between gap-3 text-sm text-slate-700"
                      >
                        <span className="flex min-w-0 items-center gap-1.5">
                          <span className="shrink-0 text-emerald-600">✓</span>
                          <span className="truncate">{target.label}</span>
                        </span>
                        <span className="shrink-0 text-xs text-slate-400">
                          {target.pages.length > 1
                            ? `${target.pages.length} pages`
                            : `p.${target.pages[0] ?? "?"}`}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {pageGroups.length > 0 && (
                  <>
                    <p className="mt-3 text-xs font-medium text-slate-400">
                      Other {DETECTION_TYPE_PLURAL[type].toLowerCase()}
                    </p>
                    <ul className="mt-1.5 space-y-1">
                      {pageGroups.map((group) => (
                        <li
                          key={group.page}
                          className="flex items-center justify-between gap-3 text-sm text-slate-600"
                        >
                          <span>Page {group.page}</span>
                          <span className="text-xs text-slate-400">
                            {group.count} detected
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            );
          })}

          {named.length === 0 && possible.length === 0 && (
            <p className="text-sm text-slate-500">
              No structured content was detected in this document.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
