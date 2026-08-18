"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CalendarClock,
  FileStack,
  Gauge,
  ListChecks,
  Plus,
  ScanText,
  ScrollText,
  ShieldAlert,
} from "lucide-react";

import DocumentResultsTable from "@/components/document-results-table";
import { getDashboardStats, listDocuments } from "@/lib/documents";
import type {
  DashboardStats,
  DocumentSummary,
} from "@/types/document";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(
    null,
  );
  const [documents, setDocuments] = useState<DocumentSummary[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const [statsResult, documentsResult] = await Promise.all([
          getDashboardStats(),
          listDocuments(10),
        ]);

        if (!active) return;

        setStats(statsResult);
        setDocuments(documentsResult);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load the dashboard.",
        );
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
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-blue-600">
            Contract Extraction
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">
            Dashboard
          </h1>
        </div>

        <Link
          href="/extraction/new"
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Extraction
        </Link>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && !stats && (
        <p className="text-sm text-slate-500">Loading...</p>
      )}

      {stats && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={FileStack}
              label="Documents Processed"
              value={stats.total_documents.toLocaleString()}
            />
            <StatCard
              icon={ShieldAlert}
              label="Contracts Pending Review"
              value={stats.review_required.toLocaleString()}
              tone="amber"
            />
            <StatCard
              icon={Gauge}
              label="Average Confidence"
              value={
                stats.extraction_accuracy !== null
                  ? `${(stats.extraction_accuracy * 100).toFixed(1)}%`
                  : "—"
              }
              tone="emerald"
            />
            <StatCard
              icon={ListChecks}
              label="Review Completion Rate"
              value={
                stats.review_completion_rate !== null
                  ? `${stats.review_completion_rate.toFixed(1)}%`
                  : "—"
              }
            />
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={ScanText}
              label="OCR Accuracy"
              value={
                stats.ocr_accuracy !== null
                  ? `${stats.ocr_accuracy.toFixed(1)}%`
                  : "—"
              }
            />
            <StatCard
              icon={ScrollText}
              label="Clause Extraction Accuracy"
              value={
                stats.clause_extraction_accuracy !== null
                  ? `${(stats.clause_extraction_accuracy * 100).toFixed(1)}%`
                  : "—"
              }
            />
            <StatCard
              icon={CalendarClock}
              label="Fields Extracted Today"
              value={stats.fields_extracted_today.toLocaleString()}
            />
            <StatCard
              icon={ShieldAlert}
              label="Documents Requiring Manual Review"
              value={stats.documents_requiring_manual_review.toLocaleString()}
              tone="amber"
            />
          </div>
        </>
      )}

      <div className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-6 py-4">
          <p className="text-sm font-semibold text-slate-900">
            Recent Extractions
          </p>
        </div>

        {documents.length === 0 && !loading ? (
          <div className="p-10 text-center text-sm text-slate-500">
            No documents yet.{" "}
            <Link
              href="/extraction/new"
              className="font-semibold text-blue-700 hover:text-blue-800"
            >
              Upload your first contract
            </Link>
            .
          </div>
        ) : (
          <DocumentResultsTable
            documents={documents}
            emptyMessage="No documents yet."
          />
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  tone = "blue",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone?: "blue" | "emerald" | "amber" | "slate";
}) {
  const toneClasses = {
    blue: "bg-blue-50 text-blue-600",
    emerald: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
    slate: "bg-slate-100 text-slate-600",
  }[tone];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div
        className={[
          "flex h-9 w-9 items-center justify-center rounded-xl",
          toneClasses,
        ].join(" ")}
      >
        <Icon className="h-5 w-5" />
      </div>

      <p className="mt-3 text-2xl font-semibold text-slate-950">
        {value}
      </p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
