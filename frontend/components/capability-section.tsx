import Link from "next/link";
import {
  ArrowRight,
  FileSearch,
  FolderOpen,
  GitBranch,
  Scale,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";

const CAPABILITIES = [
  {
    title: "Extraction",
    description:
      "Upload contracts and pull fields, tables, and clauses with source-level evidence.",
    href: "/extraction/new",
    icon: ScanSearch,
  },
  {
    title: "Repository",
    description:
      "Browse every processed agreement in one searchable contract library.",
    href: "/repository",
    icon: FolderOpen,
  },
  {
    title: "Field Explorer",
    description:
      "Compare extracted values across documents and find anomalies fast.",
    href: "/explorer",
    icon: FileSearch,
  },
  {
    title: "FAR / DFARS",
    description:
      "Locate and compare regulatory clauses with confidence and context.",
    href: "/clauses",
    icon: Scale,
  },
  {
    title: "Relationships",
    description:
      "Map parent, amendment, and related-agreement links across the portfolio.",
    href: "/relationships",
    icon: GitBranch,
  },
  {
    title: "Review",
    description:
      "Queue low-confidence fields for human verification before they ship.",
    href: "/review-queue",
    icon: ShieldCheck,
  },
] as const;

export default function CapabilitySection() {
  return (
    <section className="capability-section">
      <div className="mb-6 max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-teal">
          Platform
        </p>
        <h2 className="mt-2 text-2xl font-medium tracking-tight text-foreground sm:text-3xl">
          What Data Agent can do
        </h2>
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          Contract intelligence across extraction, discovery, compliance, and
          review — not just a single upload gateway.
        </p>
      </div>

      <div className="capability-grid">
        {CAPABILITIES.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="capability-tile group"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <item.icon className="h-5 w-5" strokeWidth={1.75} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                {item.title}
                <ArrowRight className="h-3.5 w-3.5 opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
              </p>
              <p className="mt-1 text-sm leading-5 text-text-secondary">
                {item.description}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
