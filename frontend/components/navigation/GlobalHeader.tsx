"use client";

import Link from "next/link";
import { Bell, Menu, Plus, Search, Sparkles } from "lucide-react";
import { useState } from "react";

import MobileNavigation from "@/components/navigation/MobileNavigation";
import NavDropdown from "@/components/navigation/NavDropdown";
import {
  GOVERNANCE_SECTIONS,
  INTELLIGENCE_SECTIONS,
  OVERVIEW_LINKS,
  PLATFORM_SECTIONS,
  REVIEW_SECTIONS,
} from "@/components/navigation/nav-config";

interface GlobalHeaderProps {
  onOpenSearch: () => void;
}

export default function GlobalHeader({ onOpenSearch }: GlobalHeaderProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <header className="global-header shrink-0">
        <div className="flex items-center gap-4 lg:gap-8">
          <Link href="/" className="flex shrink-0 items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sirion-teal text-[11px] font-semibold text-text-on-dark">
              CA
            </div>
            <div className="hidden min-w-0 sm:block">
              <p className="truncate text-sm font-semibold uppercase tracking-wide text-text-on-dark">
                Consult America
              </p>
              <p className="truncate text-xs text-sirion-teal-soft">
                Data Agent
              </p>
            </div>
          </Link>

          <button
            type="button"
            className="nav-menu-button ml-auto lg:hidden"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-4 w-4" strokeWidth={1.75} />
          </button>

          <nav
            className="hidden items-center gap-1 lg:flex"
            aria-label="Main navigation"
          >
            <NavDropdown
              label="Platform"
              overviewTitle="Platform Overview"
              overviewLinks={OVERVIEW_LINKS}
              sections={PLATFORM_SECTIONS}
            />
            <NavDropdown
              label="Intelligence"
              overviewTitle="Intelligence Overview"
              sections={INTELLIGENCE_SECTIONS}
            />
            <NavDropdown
              label="Review"
              overviewTitle="Review Overview"
              sections={REVIEW_SECTIONS}
            />
            <NavDropdown
              label="Governance"
              overviewTitle="Governance Overview"
              sections={GOVERNANCE_SECTIONS}
            />
          </nav>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <Link href="/extraction/new" className="btn-new-extraction hidden sm:inline-flex">
            <Plus className="h-4 w-4" strokeWidth={2} />
            New Extraction
          </Link>

          <Link href="/ask" className="btn-ask-agent hidden md:inline-flex">
            <Sparkles className="h-4 w-4" strokeWidth={1.75} />
            Ask Data Agent
          </Link>

          <button
            type="button"
            onClick={onOpenSearch}
            aria-label="Search"
            className="nav-icon-button"
          >
            <Search className="h-4 w-4" strokeWidth={1.75} />
          </button>

          <button type="button" aria-label="Notifications" className="nav-icon-button">
            <Bell className="h-4 w-4" strokeWidth={1.75} />
          </button>

          <div className="hidden items-center gap-2 border-l border-white/10 pl-3 sm:flex">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-text-on-dark">
              CA
            </div>
          </div>
        </div>
      </header>

      <MobileNavigation open={mobileOpen} onClose={() => setMobileOpen(false)} />
    </>
  );
}
