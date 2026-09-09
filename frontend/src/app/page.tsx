"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Loader2, Sparkles, Upload } from "lucide-react";

import AnimatedWorkflowDiagram from "@/components/illustrations/animated-workflow-diagram";
import CapabilitySection from "@/components/capability-section";
import DocumentResultsTable from "@/components/document-results-table";
import HeroExtractionPreview from "@/components/illustrations/hero-extraction-preview";
import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";
import { getDashboardStats, listDocuments } from "@/lib/documents";
import type { DashboardStats, DocumentSummary } from "@/types/document";

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recent, setRecent] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    Promise.all([getDashboardStats(), listDocuments(10)])
      .then(([statsResult, docs]) => {
        if (!active) return;
        setStats(statsResult);
        setRecent(docs);
      })
      .catch(() => {
        if (active) {
          setStats(null);
          setRecent([]);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <>
      <PageHero
        eyebrow="Consult America Data Agent"
        title={
          <>
            Document Intelligence
            <br />
            with confidence and precision
          </>
        }
        description="Extract, verify, search and understand critical information across contracts, financial documents and complex business records."
        specialization={
          <Link
            href="/clauses"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-text-teal transition hover:text-primary"
          >
            Contract Intelligence
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        }
        actions={
          <>
            <Link href="/extraction/new" className="btn-hero-primary">
              <Upload className="h-4 w-4 shrink-0" />
              <span className="whitespace-nowrap">New Extraction</span>
            </Link>
            <Link href="/ask" className="btn-hero-secondary">
              <Sparkles className="h-4 w-4 shrink-0" />
              <span className="whitespace-nowrap">Ask Data Agent</span>
              <ArrowRight className="h-4 w-4 shrink-0" />
            </Link>
          </>
        }
        visual={<HeroExtractionPreview />}
      />

      <ContentSection>
        <section className="mb-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-teal">
            How it works
          </p>
          <h2 className="mt-2 text-lg font-medium text-foreground">
            From upload to verified repository
          </h2>
          <div className="mt-4">
            <AnimatedWorkflowDiagram />
          </div>
        </section>

        <CapabilitySection />

        {loading ? (
          <div className="mt-14 flex items-center gap-2 text-sm text-text-secondary">
            <Loader2 className="h-4 w-4 animate-spin" />
            Building document intelligence...
          </div>
        ) : stats ? (
          <>
            <section className="mt-14">
              <h2 className="mb-4 text-lg font-medium text-foreground">
                Operational metrics
              </h2>
              <div className="metric-grid">
                <MetricCell label="Documents" value={stats.total_documents} />
                <MetricCell label="Completed" value={stats.completed} />
                <MetricCell
                  label="Review Required"
                  value={stats.review_required}
                  highlight
                />
                <MetricCell label="Processing" value={stats.processing} />
                <MetricCell
                  label="Extraction Accuracy"
                  value={
                    stats.extraction_accuracy !== null
                      ? `${Math.round(stats.extraction_accuracy * 100)}%`
                      : "—"
                  }
                />
                <MetricCell
                  label="Avg Processing"
                  value={
                    stats.average_processing_seconds !== null
                      ? `${Math.round(stats.average_processing_seconds)}s`
                      : "—"
                  }
                />
                <MetricCell
                  label="Human Review Rate"
                  value={
                    stats.human_review_rate !== null
                      ? `${stats.human_review_rate.toFixed(1)}%`
                      : "—"
                  }
                />
                <MetricCell
                  label="Fields Extracted"
                  value={stats.fields_extracted}
                />
              </div>
            </section>

            <section id="recent-extractions" className="mt-14 scroll-mt-24">
              <div className="mb-4 flex items-end justify-between gap-4">
                <h2 className="text-lg font-medium text-foreground">
                  Recent extractions
                </h2>
                <Link
                  href="/repository"
                  className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-foreground"
                >
                  View repository
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
              <div className="editorial-card overflow-hidden">
                <DocumentResultsTable
                  documents={recent}
                  emptyMessage="No documents yet. Upload a contract to begin extraction."
                  dashboardMode
                />
              </div>
            </section>

            {stats.review_required > 0 && (
              <section className="mt-14">
                <h2 className="mb-4 text-lg font-medium text-foreground">
                  Needs your attention
                </h2>
                <div className="editorial-card editorial-card-interactive flex flex-wrap items-center justify-between gap-6 p-8">
                  <div>
                    <p className="text-3xl font-medium text-foreground">
                      {stats.review_required}
                    </p>
                    <p className="mt-1 text-sm text-text-secondary">
                      contracts in the review queue
                    </p>
                  </div>
                  <Link href="/review-queue" className="btn-primary">
                    Open Review Queue
                  </Link>
                </div>
              </section>
            )}
          </>
        ) : null}
      </ContentSection>
    </>
  );
}

function MetricCell({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: number | string;
  highlight?: boolean;
}) {
  return (
    <div className="metric-cell">
      <p
        className={[
          "text-2xl font-medium tabular-nums tracking-tight",
          highlight ? "text-warning" : "text-foreground",
        ].join(" ")}
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      <p className="mt-2 text-sm text-text-secondary">{label}</p>
    </div>
  );
}
