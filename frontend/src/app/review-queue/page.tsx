"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCheck,
  CheckCircle2,
  HelpCircle,
  Inbox,
  RefreshCw,
  Search,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import PageHeader from "@/components/page-header";
import ConfidenceBadge from "@/components/confidence-badge";
import { acceptAllMetadataFields, getReviewQueue } from "@/lib/documents";
import {
  DOCUMENT_TYPE_OPTIONS,
  type ReviewQueueBucket,
  type ReviewQueueEntry,
} from "@/types/document";

const DEFAULT_REVIEWER = "Consult America";

const SECTIONS: {
  bucket: ReviewQueueBucket;
  label: string;
  description: string;
  icon: typeof CheckCircle2;
  tone: string;
  chipActive: string;
}[] = [
  {
    bucket: "high",
    label: "High Confidence",
    description: "Fields extracted cleanly — spot-check and accept.",
    icon: CheckCircle2,
    tone: "text-emerald-600",
    chipActive: "bg-emerald-600 text-white",
  },
  {
    bucket: "medium",
    label: "Medium Confidence",
    description: "Worth a closer look before accepting.",
    icon: AlertTriangle,
    tone: "text-amber-600",
    chipActive: "bg-amber-600 text-white",
  },
  {
    bucket: "low",
    label: "Low Confidence",
    description: "Extraction struggled — review carefully.",
    icon: AlertTriangle,
    tone: "text-red-600",
    chipActive: "bg-red-600 text-white",
  },
  {
    bucket: "rejected",
    label: "Rejected",
    description: "At least one field was rejected by a reviewer.",
    icon: XCircle,
    tone: "text-red-600",
    chipActive: "bg-red-600 text-white",
  },
  {
    bucket: "unknown",
    label: "Unknown",
    description: "Marked unknown and needs a human decision.",
    icon: HelpCircle,
    tone: "text-slate-500",
    chipActive: "bg-slate-600 text-white",
  },
];

export default function ReviewQueuePage() {
  const [entries, setEntries] = useState<ReviewQueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [query, setQuery] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [activeBucket, setActiveBucket] = useState<
    ReviewQueueBucket | "all"
  >("all");

  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});

  async function load(active: () => boolean = () => true) {
    setLoading(true);
    setError("");

    try {
      const result = await getReviewQueue();
      if (active()) setEntries(result);
    } catch (err) {
      if (active()) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load the review queue.",
        );
      }
    } finally {
      if (active()) setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    load(() => active);

    return () => {
      active = false;
    };
  }, []);

  const documentTypesInQueue = useMemo(
    () =>
      DOCUMENT_TYPE_OPTIONS.filter((option) =>
        entries.some((entry) => entry.document_type === option),
      ),
    [entries],
  );

  const filteredEntries = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return entries.filter((entry) => {
      if (
        normalizedQuery &&
        !entry.original_filename.toLowerCase().includes(normalizedQuery)
      ) {
        return false;
      }

      if (documentType && entry.document_type !== documentType) {
        return false;
      }

      return true;
    });
  }, [entries, query, documentType]);

  const bucketCounts = useMemo(() => {
    const counts: Record<ReviewQueueBucket, number> = {
      high: 0,
      medium: 0,
      low: 0,
      rejected: 0,
      unknown: 0,
    };

    for (const entry of filteredEntries) {
      counts[entry.queue_bucket] += 1;
    }

    return counts;
  }, [filteredEntries]);

  async function handleAcceptAll(entry: ReviewQueueEntry) {
    setAcceptingId(entry.document_id);
    setRowErrors((current) => {
      const next = { ...current };
      delete next[entry.document_id];
      return next;
    });

    try {
      await acceptAllMetadataFields(entry.document_id, DEFAULT_REVIEWER);
      setEntries((current) =>
        current.filter((item) => item.document_id !== entry.document_id),
      );
    } catch (err) {
      setRowErrors((current) => ({
        ...current,
        [entry.document_id]:
          err instanceof Error
            ? err.message
            : "Unable to accept all fields.",
      }));
    } finally {
      setAcceptingId(null);
    }
  }

  const visibleSections = SECTIONS.filter(
    (section) =>
      activeBucket === "all" || activeBucket === section.bucket,
  );

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <PageHeader
        title="Review Queue"
        description="Complete human review for extracted contract fields."
        actions={
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-semibold text-foreground transition hover:bg-background disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setActiveBucket("all")}
          className={[
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition",
            activeBucket === "all"
              ? "bg-blue-600 text-white"
              : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200",
          ].join(" ")}
        >
          All
          <span
            className={
              activeBucket === "all" ? "text-blue-100" : "text-slate-400"
            }
          >
            {filteredEntries.length}
          </span>
        </button>

        {SECTIONS.map((section) => (
          <button
            key={section.bucket}
            type="button"
            onClick={() =>
              setActiveBucket((current) =>
                current === section.bucket ? "all" : section.bucket,
              )
            }
            className={[
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
              activeBucket === section.bucket
                ? `${section.chipActive} border-transparent`
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-100",
            ].join(" ")}
          >
            <section.icon className="h-3.5 w-3.5" />
            {section.label}
            <span
              className={
                activeBucket === section.bucket
                  ? "opacity-80"
                  : "text-slate-400"
              }
            >
              {bucketCounts[section.bucket]}
            </span>
          </button>
        ))}
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by filename..."
            className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-800"
          />
        </div>

        <select
          value={documentType}
          onChange={(event) => setDocumentType(event.target.value)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">All types</option>
          {documentTypesInQueue.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && entries.length === 0 && (
        <div className="space-y-3">
          {[0, 1, 2].map((index) => (
            <div
              key={index}
              className="h-16 animate-pulse rounded-2xl border border-slate-200 bg-slate-100"
            />
          ))}
        </div>
      )}

      {!loading && entries.length === 0 && !error && (
        <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-slate-200 py-16 text-center">
          <Inbox className="h-8 w-8 text-slate-300" />
          <p className="text-sm font-medium text-slate-600">
            The review queue is empty.
          </p>
          <p className="text-xs text-slate-400">
            Every uploaded document has been fully reviewed.
          </p>
        </div>
      )}

      {!loading &&
        entries.length > 0 &&
        filteredEntries.length === 0 &&
        !error && (
          <p className="rounded-2xl border border-dashed border-slate-200 py-10 text-center text-sm text-slate-500">
            No documents match your filters.
          </p>
        )}

      <div className="space-y-6">
        {visibleSections.map((section) => {
          const sectionEntries = filteredEntries.filter(
            (entry) => entry.queue_bucket === section.bucket,
          );

          if (sectionEntries.length === 0) return null;

          return (
            <div
              key={section.bucket}
              className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
            >
              <div className="flex items-center gap-2 border-b border-slate-200 px-6 py-4">
                <section.icon className={`h-4 w-4 ${section.tone}`} />
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    {section.label}
                    <span className="ml-2 text-xs font-normal text-slate-400">
                      {sectionEntries.length}
                    </span>
                  </p>
                  <p className="text-xs text-slate-400">
                    {section.description}
                  </p>
                </div>
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
                        {entry.document_type ?? "Unclassified"} ·{" "}
                        {new Date(entry.uploaded_at).toLocaleDateString()}
                      </p>
                      {rowErrors[entry.document_id] && (
                        <p className="mt-1 text-xs text-red-600">
                          {rowErrors[entry.document_id]}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      {entry.confidence !== null && (
                        <ConfidenceBadge confidence={entry.confidence} />
                      )}

                      <button
                        type="button"
                        onClick={() => handleAcceptAll(entry)}
                        disabled={acceptingId === entry.document_id}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <CheckCheck className="h-3.5 w-3.5" />
                        {acceptingId === entry.document_id
                          ? "Accepting..."
                          : "Accept All"}
                      </button>

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
