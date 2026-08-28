"use client";

import { useEffect, useState } from "react";
import { GitBranch, List, Loader2 } from "lucide-react";

import ContractHierarchy from "@/components/contract-hierarchy";
import DocumentResultsTable from "@/components/document-results-table";
import EmptyState from "@/components/illustrations/empty-state";
import { LoadingState } from "@/components/layout/StatusState";
import PageHeader from "@/components/page-header";
import { getDocumentHierarchy, searchDocuments } from "@/lib/documents";
import type { DocumentSummary, HierarchyNode } from "@/types/document";

type ViewMode = "tree" | "table";

export default function RelationshipsPage() {
  const [view, setView] = useState<ViewMode>("tree");
  const [roots, setRoots] = useState<HierarchyNode[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);

      try {
        const [hierarchy, search] = await Promise.all([
          getDocumentHierarchy(),
          searchDocuments({ limit: 50 }),
        ]);

        if (!active) return;
        setRoots(hierarchy.roots);
        setDocuments(
          search.documents.filter((doc) => Boolean(doc.relationship)),
        );
      } catch {
        if (active) {
          setRoots([]);
          setDocuments([]);
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

  const relatedCount = documents.length;

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <PageHeader
        title="Contract Relationships"
        description="Explore parent-child contract hierarchies and related documents."
      />

      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-text-secondary">
          {relatedCount} documents with detected relationships
        </p>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-surface p-1">
          <button
            type="button"
            onClick={() => setView("tree")}
            className={[
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition",
              view === "tree"
                ? "bg-brand-blue text-white"
                : "text-text-secondary hover:bg-background",
            ].join(" ")}
          >
            <GitBranch className="h-3.5 w-3.5" />
            Tree
          </button>
          <button
            type="button"
            onClick={() => setView("table")}
            className={[
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition",
              view === "table"
                ? "bg-brand-blue text-white"
                : "text-text-secondary hover:bg-background",
            ].join(" ")}
          >
            <List className="h-3.5 w-3.5" />
            Table
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-surface">
        {loading ? (
          <LoadingState
            title="Detecting document relationships..."
            description="Analyzing parent-child contracts, SOWs, task orders, and amendment lineages."
          />
        ) : view === "tree" ? (
          roots.length > 0 ? (
            <ContractHierarchy roots={roots} />
          ) : (
            <EmptyState
              variant="relationships"
              title="No document relationships detected"
              description="Upload master agreements and related amendments to view contract trees and dependencies."
            />
          )
        ) : (
          <DocumentResultsTable
            documents={documents}
            emptyMessage="No related documents found."
            showExtendedColumns
          />
        )}
      </div>
    </div>
  );
}
