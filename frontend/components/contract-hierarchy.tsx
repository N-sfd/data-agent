"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { HierarchyNode } from "@/types/document";

interface ContractHierarchyProps {
  roots: HierarchyNode[];
}

const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  amendment_of: "Amendment",
  change_order_of: "Change Order",
  sow_of: "Statement of Work",
  subcontract_of: "Subcontract",
};

export default function ContractHierarchy({
  roots,
}: ContractHierarchyProps) {
  if (roots.length === 0) {
    return (
      <div className="px-8 py-16 text-center text-[15px] text-text-secondary">
        No contract relationships have been confirmed yet.
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      {roots.map((root) => (
        <TreeNode key={root.document_id} node={root} depth={0} />
      ))}
    </div>
  );
}

function TreeNode({
  node,
  depth,
}: {
  node: HierarchyNode;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children.length > 0;

  return (
    <div style={{ marginLeft: depth * 24 }}>
      <div className="editorial-card flex items-start gap-3 p-5 transition duration-200 hover:shadow-[var(--shadow-elevated)]">
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="mt-0.5 text-text-secondary transition hover:text-foreground"
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}

        <div className="min-w-0 flex-1">
          <Link
            href={`/documents/${node.document_id}/review`}
            className="text-[15px] font-medium text-foreground hover:underline"
          >
            {node.title}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-secondary">
            {node.relationship_type && (
              <span>
                {RELATIONSHIP_TYPE_LABELS[node.relationship_type] ??
                  node.relationship_type}
              </span>
            )}
            {node.document_number && <span>{node.document_number}</span>}
            {node.document_type && <span>{node.document_type}</span>}
          </div>
        </div>
      </div>

      {expanded && hasChildren && (
        <div className="relative mt-4 space-y-4 border-l border-border/80 pl-6">
          {node.children.map((child) => (
            <TreeNode key={child.document_id} node={child} depth={0} />
          ))}
        </div>
      )}
    </div>
  );
}
