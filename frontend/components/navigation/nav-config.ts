import type { LucideIcon } from "lucide-react";
import {
  Archive,
  ClipboardList,
  Compass,
  FileSearch,
  GitBranch,
  GitCompare,
  History,
  Key,
  ListChecks,
  ScrollText,
  Search,
  Settings,
  Sparkles,
  Workflow,
} from "lucide-react";

export interface NavTile {
  label: string;
  description?: string;
  href: string;
  icon: LucideIcon;
}

export interface MegaMenuSection {
  title: string;
  tiles: NavTile[];
}

export const PLATFORM_SECTIONS: MegaMenuSection[] = [
  {
    title: "Document Intelligence",
    tiles: [
      {
        label: "Extraction",
        description: "Upload and extract with source verification",
        href: "/extraction/new",
        icon: FileSearch,
      },
      {
        label: "Repository",
        description: "Browse all documents and metadata",
        href: "/repository",
        icon: Archive,
      },
      {
        label: "Field Explorer",
        description: "Compare fields across documents",
        href: "/explorer",
        icon: Compass,
      },
      {
        label: "Ask Data Agent",
        description: "Source-grounded questions across the repository",
        href: "/ask",
        icon: Sparkles,
      },
      {
        label: "Review Queue",
        description: "Items that need human verification",
        href: "/review-queue",
        icon: ListChecks,
      },
      {
        label: "Search",
        description: "Search documents, fields, and evidence",
        href: "/search",
        icon: Search,
      },
    ],
  },
  {
    title: "Contract Intelligence",
    tiles: [
      {
        label: "FAR / DFARS",
        description: "Federal acquisition clause intelligence",
        href: "/clauses",
        icon: ScrollText,
      },
      {
        label: "Relationships",
        description: "Parent, child, and amendment hierarchy",
        href: "/relationships",
        icon: GitBranch,
      },
    ],
  },
];

export const INTELLIGENCE_SECTIONS: MegaMenuSection[] = [
  {
    title: "Document Intelligence",
    tiles: [
      {
        label: "Field Explorer",
        description: "Cross-document field comparison",
        href: "/explorer",
        icon: Compass,
      },
      {
        label: "Ask Data Agent",
        description: "Source-grounded answers across documents",
        href: "/ask",
        icon: Sparkles,
      },
    ],
  },
  {
    title: "Contract Intelligence",
    tiles: [
      {
        label: "FAR / DFARS Clauses",
        description: "Federal acquisition clause intelligence",
        href: "/clauses",
        icon: ScrollText,
      },
      {
        label: "Clause Search",
        description: "Search provisions across agreements",
        href: "/clauses",
        icon: Search,
      },
      {
        label: "Clause Comparison",
        description: "Compare clauses side by side",
        href: "/clauses/compare",
        icon: GitCompare,
      },
      {
        label: "Relationships",
        description: "Contract hierarchy and lineage",
        href: "/relationships",
        icon: GitBranch,
      },
    ],
  },
];

export const REVIEW_SECTIONS: MegaMenuSection[] = [
  {
    title: "Review",
    tiles: [
      {
        label: "Review Queue",
        description: "Low confidence, conflicts, and corrections",
        href: "/review-queue",
        icon: ListChecks,
      },
      {
        label: "Recent Extractions",
        description: "Latest uploaded and processed documents",
        href: "/#recent-extractions",
        icon: Archive,
      },
      {
        label: "Human Review History",
        description: "Audit trail of review actions",
        href: "/audit-log",
        icon: History,
      },
    ],
  },
];

export const GOVERNANCE_SECTIONS: MegaMenuSection[] = [
  {
    title: "Governance",
    tiles: [
      {
        label: "Integration Center",
        description: "Oracle ERP, n8n workflows & approved data",
        href: "/integrations",
        icon: Workflow,
      },
      {
        label: "Audit Log",
        description: "Track all review and edit actions",
        href: "/audit-log",
        icon: ClipboardList,
      },
      {
        label: "Settings",
        description: "Application and extraction settings",
        href: "/settings",
        icon: Settings,
      },
      {
        label: "API Keys",
        description: "Manage integration credentials",
        href: "/api-keys",
        icon: Key,
      },
    ],
  },
];

export const OVERVIEW_LINKS = [
  { label: "Data Agent", href: "/", icon: Sparkles },
  { label: "API Keys", href: "/api-keys", icon: Key },
];
