"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import { getReviewQueue } from "@/lib/documents";
import type {
  ReviewQueueBucket,
  ReviewQueueEntry,
} from "@/types/document";

const SECTIONS: {
  bucket: ReviewQueueBucket;
  label: string;
  icon: typeof CheckCircle2;
  tone: string;
}[] = [
  {
    bucket: "high",
    label: "High Confidence",
    icon: CheckCircle2,
    tone: "text-emerald-600",
  },
  {
    bucket: "medium",
    label: "Medium Confidence",
    icon: AlertTriangle,
    tone: "text-amber-600",
  },
  {
    bucket: "low",
    label: "Low Confidence",
    icon: AlertTriangle,
    tone: "text-red-600",
  },
  {
    bucket: "rejected",
    label: "Rejected",
    icon: XCircle,
    tone: "text-red-600",
  },
  {
    bucket: "unknown",
    label: "Unknown",
    icon: HelpCircle,
    tone: "text-slate-500",
  },
];

export default function ReviewQueuePage() {
  const [entries, setEntries] = useState<ReviewQueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const result = await getReviewQueue();
        if (active) setEntries(result);
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load the review queue.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8 flex items-center gap-2">
        <ShieldAlert className="h-5 w-5 text-blue-600" />
        <div>
          <p className="text-sm font-semibold text-blue-600">
            Contract Extraction
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">
            Review Queue
          </h1>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && entries.length === 0 && (
        <p className="text-sm text-slate-500">Loading...</p>
      )}

      {!loading && entries.length === 0 && !error && (
        <p className="text-sm text-slate-500">
          No documents yet.
        </p>
      )}

      <div className="space-y-6">
        {SECTIONS.map((section) => {
          const sectionEntries = entries.filter(
            (entry) => entry.queue_bucket === section.bucket,
          );

          if (sectionEntries.length === 0) return null;

          return (
            <div
              key={section.bucket}
              className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
            >
              <div className="flex items-center gap-2 border-b border-slate-200 px-6 py-4">
                <section.icon
                  className={`h-4 w-4 ${section.tone}`}
                />
                <p className="text-sm font-semibold text-slate-900">
                  {section.label}
                </p>
                <span className="text-xs text-slate-400">
                  {sectionEntries.length}
                </span>
              </div>

              <div className="divide-y divide-slate-100">
                {sectionEntries.map((entry) => (
                  <div
                    key={entry.document_id}
                    className="flex flex-wrap items-center justify-between gap-3 px-6 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-800">
                        {entry.original_filename}
                      </p>
                      <p className="text-xs text-slate-400">
                        {entry.document_type ?? "Unclassified"}
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      {entry.confidence !== null && (
                        <ConfidenceBadge
                          confidence={entry.confidence}
                        />
                      )}

                      <Link
                        href={`/documents/${entry.document_id}/review`}
                        className="text-xs font-semibold text-blue-700 hover:text-blue-800"
                      >
                        Review
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
