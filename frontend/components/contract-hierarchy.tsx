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
      <div className="p-10 text-center text-sm text-slate-500">
        No contract relationships have been confirmed yet.
      </div>
    );
  }

  return (
    <div className="divide-y divide-slate-100">
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
    <div>
      <div
        className="flex items-center gap-2 px-6 py-3 hover:bg-slate-50"
        style={{ paddingLeft: `${24 + depth * 24}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="text-slate-400 hover:text-slate-700"
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

        <Link
          href={`/documents/${node.document_id}/review`}
          className="font-medium text-blue-700 hover:text-blue-800"
        >
          {node.title}
        </Link>

        {node.relationship_type && (
          <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
            {RELATIONSHIP_TYPE_LABELS[node.relationship_type] ??
              node.relationship_type}
          </span>
        )}

        {node.document_number && (
          <span className="text-xs text-slate-400">
            {node.document_number}
          </span>
        )}

        {node.relationship_status && (
          <span className="ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            {node.relationship_status}
          </span>
        )}
      </div>

      {expanded &&
        node.children.map((child) => (
          <TreeNode
            key={child.document_id}
            node={child}
            depth={depth + 1}
          />
        ))}
    </div>
  );
}
