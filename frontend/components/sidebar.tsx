"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Archive,
  BarChart3,
  Building2,
  ClipboardList,
  FileSearch,
  FileText,
  LayoutDashboard,
  ListChecks,
  Search,
  Settings,
  type LucideIcon,
} from "lucide-react";

interface NavLink {
  label: string;
  icon: LucideIcon;
  href: string;
}

interface DisabledItem {
  label: string;
  icon: LucideIcon;
}

const PRIMARY_LINK: NavLink = {
  label: "Dashboard",
  icon: LayoutDashboard,
  href: "/",
};

const STORE_LINKS: NavLink[] = [
  { label: "Extraction", icon: FileSearch, href: "/extraction/new" },
  { label: "Review Queue", icon: ListChecks, href: "/review-queue" },
  { label: "Repository", icon: Archive, href: "/repository" },
  { label: "Search", icon: Search, href: "/search" },
  { label: "Audit Log", icon: ClipboardList, href: "/audit-log" },
];

const STORE_DISABLED: DisabledItem[] = [];

const BOTTOM_LINKS: NavLink[] = [
  { label: "Settings", icon: Settings, href: "/settings/extraction-models" },
];

const BOTTOM_DISABLED: DisabledItem[] = [
  { label: "Contracts", icon: FileText },
  { label: "Suppliers", icon: Building2 },
  { label: "Analytics", icon: BarChart3 },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full min-h-0 w-64 shrink-0 flex-col self-stretch bg-slate-900 text-slate-300">
      <div className="flex h-16 shrink-0 items-center gap-2 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
          D
        </div>
        <span className="text-sm font-semibold tracking-wide text-white">
          Data Agent
        </span>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-6">
        <NavItem link={PRIMARY_LINK} pathname={pathname} />

        <div>
          <p className="px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Store
          </p>

          <div className="mt-2 space-y-1">
            {STORE_LINKS.map((link) => (
              <NavItem
                key={link.label}
                link={link}
                pathname={pathname}
              />
            ))}
            {STORE_DISABLED.map((item) => (
              <DisabledNavItem key={item.label} item={item} />
            ))}
          </div>
        </div>

        <div className="space-y-1 border-t border-slate-800 pt-4">
          {BOTTOM_LINKS.map((link) => (
            <NavItem
              key={link.label}
              link={link}
              pathname={pathname}
            />
          ))}
          {BOTTOM_DISABLED.map((item) => (
            <DisabledNavItem key={item.label} item={item} />
          ))}
        </div>
      </nav>
    </aside>
  );
}

function NavItem({
  link,
  pathname,
}: {
  link: NavLink;
  pathname: string;
}) {
  const active = pathname === link.href;

  return (
    <Link
      href={link.href}
      className={[
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
        active
          ? "bg-slate-800 text-white"
          : "text-slate-300 hover:bg-slate-800/60 hover:text-white",
      ].join(" ")}
    >
      <link.icon className="h-4 w-4" />
      {link.label}
    </Link>
  );
}

function DisabledNavItem({ item }: { item: DisabledItem }) {
  return (
    <div
      aria-disabled="true"
      title="Coming soon"
      className="flex cursor-not-allowed items-center justify-between rounded-lg px-3 py-2 text-sm text-slate-500"
    >
      <span className="flex items-center gap-3">
        <item.icon className="h-4 w-4" />
        {item.label}
      </span>

      <span className="rounded-full bg-slate-800 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
        Soon
      </span>
    </div>
  );
}
