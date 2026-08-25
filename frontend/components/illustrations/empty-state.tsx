import type { ReactNode } from "react";
import {
  FileSearch,
  FileText,
  GitBranch,
  Inbox,
  Scale,
  Table2,
} from "lucide-react";

export type EmptyStateVariant =
  | "documents"
  | "relationships"
  | "clauses"
  | "extraction-results"
  | "fields"
  | "queue";

const VARIANT_CONFIG: Record<
  EmptyStateVariant,
  { Icon: typeof FileText; label: string }
> = {
  documents: { Icon: FileText, label: "No documents" },
  relationships: { Icon: GitBranch, label: "No relationships" },
  clauses: { Icon: Scale, label: "No clauses found" },
  "extraction-results": { Icon: Table2, label: "No extraction results" },
  fields: { Icon: FileSearch, label: "No fields found" },
  queue: { Icon: Inbox, label: "Queue empty" },
};

interface EmptyStateProps {
  variant: EmptyStateVariant;
  title?: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export default function EmptyState({
  variant,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  const { Icon, label } = VARIANT_CONFIG[variant];

  return (
    <div
      className={[
        "empty-state flex flex-col items-center px-6 py-12 text-center sm:py-16",
        className,
      ].join(" ")}
    >
      <div className="empty-state-art" aria-hidden>
        <svg viewBox="0 0 120 80" className="h-16 w-24 opacity-90">
          <ellipse cx="60" cy="68" rx="36" ry="6" fill="currentColor" className="text-border/60" />
          <rect
            x="28"
            y="12"
            width="64"
            height="48"
            rx="6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="text-border"
          />
          <line x1="38" y1="26" x2="82" y2="26" stroke="currentColor" strokeWidth="2" className="text-primary/25" />
          <line x1="38" y1="36" x2="74" y2="36" stroke="currentColor" strokeWidth="1.5" className="text-border/80" />
          <line x1="38" y1="44" x2="78" y2="44" stroke="currentColor" strokeWidth="1.5" className="text-border/60" />
        </svg>
        <span className="empty-state-icon-badge">
          <Icon className="h-4 w-4" strokeWidth={1.75} />
        </span>
      </div>

      <p className="mt-4 text-sm font-medium text-foreground">
        {title ?? label}
      </p>
      <p className="mt-1.5 max-w-sm text-sm leading-6 text-text-secondary">
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
