import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  Archive,
  CircleAlert,
  FileText,
  GraduationCap,
  LayoutGrid,
  Mail,
  Receipt,
  Upload,
  BarChart3,
  ClipboardList,
  Compass,
  FileSearch,
  GitBranch,
  GitCompare,
  History,
  Layers,
  Lightbulb,
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

export const DOCUMENTS_SECTIONS: MegaMenuSection[] = [
  {
    title: "Documents",
    tiles: [
      {
        label: "All documents",
        description: "Every document in your workspace",
        href: "/documents",
        icon: Archive,
      },
      {
        label: "Needs review",
        description: "Documents with values to confirm",
        href: "/documents?filter=review",
        icon: ListChecks,
      },
      {
        label: "Failed",
        description: "Documents whose processing did not complete",
        href: "/documents?filter=failed",
        icon: CircleAlert,
      },
      {
        label: "Upload document",
        description: "Add a document and let Data Agent detect its type",
        href: "/extraction/new",
        icon: Upload,
      },
    ],
  },
  {
    title: "By type",
    tiles: [
      { label: "Invoices", href: "/documents?family=invoice", icon: Receipt },
      { label: "Transcripts & certificates", href: "/documents?family=academic_transcript", icon: GraduationCap },
      { label: "Contracts", href: "/documents?family=government_contract", icon: FileText },
      { label: "FAR regulations", href: "/documents?family=far_regulation", icon: ScrollText },
      { label: "Correspondence", href: "/documents?family=correspondence", icon: Mail },
    ],
  },
];

export const PLATFORM_SECTIONS: MegaMenuSection[] = [
  {
    title: "Document Intelligence",
    tiles: [
      {
        label: "Documents",
        description: "Open any document workspace",
        href: "/documents",
        icon: Archive,
      },
      {
        label: "New Document",
        description: "Upload and let Data Agent detect the profile",
        href: "/extraction/new",
        icon: FileSearch,
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
        label: "Review",
        description: "Fields that need a human decision",
        href: "/review-queue",
        icon: ListChecks,
      },
      {
        label: "Search",
        description: "Search documents, fields, and evidence",
        href: "/search",
        icon: Search,
      },
      {
        label: "Analytics",
        description: "Portfolio analytics, extraction quality, and review performance",
        href: "/analytics",
        icon: BarChart3,
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
        description: "Search FAR/DFARS provisions across contracts",
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
      {
        label: "Contract Insights",
        description: "Executive summaries and portfolio intelligence",
        href: "/insights",
        icon: Lightbulb,
      },
    ],
  },
];

export const REVIEW_SECTIONS: MegaMenuSection[] = [
  {
    title: "Review",
    tiles: [
      {
        label: "Review",
        description: "Extraction, validation, missing values, and conflicts",
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
      {
        label: "Activity Feed",
        description: "Live feed of recent review and edit actions",
        href: "/activity",
        icon: Activity,
      },
    ],
  },
];

export const GOVERNANCE_SECTIONS: MegaMenuSection[] = [
  {
    title: "Governance",
    tiles: [
      {
        label: "Architecture",
        description: "Platform lifecycle, trust loop, and deploy topology",
        href: "/architecture",
        icon: Layers,
      },
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
        label: "Risk",
        description: "Contract risk patterns, obligations, and compliance gaps",
        href: "/risk",
        icon: AlertTriangle,
      },
    ],
  },
];

export const OVERVIEW_LINKS = [
  { label: "Data Agent", href: "/", icon: Sparkles },
];

export interface TopMenu {
  id: "documents" | "platform" | "intelligence" | "review" | "governance";
  label: string;
  /** The hub the label itself opens. */
  href: string;
  description: string;
  sections: MegaMenuSection[];
}

export const TOP_MENUS: TopMenu[] = [
  {
    id: "documents",
    label: "Documents",
    href: "/documents",
    description: "Every document, by status and type.",
    sections: DOCUMENTS_SECTIONS,
  },
  {
    id: "platform",
    label: "Platform",
    href: "/platform",
    description: "Upload, extract, explore and analyze documents.",
    sections: PLATFORM_SECTIONS,
  },
  {
    id: "intelligence",
    label: "Intelligence",
    href: "/intelligence",
    description: "Cross-document answers, clause intelligence and contract insights.",
    sections: INTELLIGENCE_SECTIONS,
  },
  {
    id: "review",
    label: "Review",
    href: "/review",
    description: "Human review of extracted values and the record of every decision.",
    sections: REVIEW_SECTIONS,
  },
  {
    id: "governance",
    label: "Governance",
    href: "/governance",
    description: "Risk, audit, integrations, architecture and settings.",
    sections: GOVERNANCE_SECTIONS,
  },
];

export function topMenu(id: TopMenu["id"]): TopMenu {
  return TOP_MENUS.find((menu) => menu.id === id) as TopMenu;
}

export const HUB_ICON = LayoutGrid;
