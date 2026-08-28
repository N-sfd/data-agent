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
    title: "Store",
    tiles: [
      {
        label: "Extraction",
        description: "Upload and extract contract intelligence",
        href: "/extraction/new",
        icon: FileSearch,
      },
      {
        label: "Repository",
        description: "Browse all agreements and metadata",
        href: "/repository",
        icon: Archive,
      },
      {
        label: "Search",
        description: "Search contracts, fields, and clauses",
        href: "/search",
        icon: Search,
      },
    ],
  },
  {
    title: "Contract Intelligence",
    tiles: [
      {
        label: "Field Explorer",
        description: "Analyze fields across the repository",
        href: "/explorer",
        icon: Compass,
      },
      {
        label: "Relationships",
        description: "Parent, child, and amendment hierarchy",
        href: "/relationships",
        icon: GitBranch,
      },
      {
        label: "Review Queue",
        description: "Documents awaiting human review",
        href: "/review-queue",
        icon: ListChecks,
      },
    ],
  },
];

export const INTELLIGENCE_SECTIONS: MegaMenuSection[] = [
  {
    title: "Intelligence",
    tiles: [
      {
        label: "Field Explorer",
        description: "Cross-contract field analysis",
        href: "/explorer",
        icon: Compass,
      },
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
        description: "Pending human review items",
        href: "/review-queue",
        icon: ListChecks,
      },
      {
        label: "Extraction Review",
        description: "Validate extracted contract fields",
        href: "/review-queue",
        icon: FileSearch,
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
