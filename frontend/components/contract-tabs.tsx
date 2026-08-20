"use client";

const TABS = [
  "Overview",
  "Data",
  "Clauses",
  "Relationships",
  "Documents",
  "Activity",
] as const;

export type ContractTab = (typeof TABS)[number];

interface ContractTabsProps {
  active: ContractTab;
  onChange: (tab: ContractTab) => void;
}

export default function ContractTabs({ active, onChange }: ContractTabsProps) {
  return (
    <div className="flex shrink-0 gap-6 overflow-x-auto border-b border-border/80 bg-surface px-6 sm:px-8">
      {TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          onClick={() => onChange(tab)}
          className={[
            "shrink-0 border-b-2 py-4 text-sm font-medium transition duration-200",
            active === tab
              ? "border-navy text-foreground"
              : "border-transparent text-text-secondary hover:text-foreground",
          ].join(" ")}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}

export { TABS };
