"use client";

import Image from "next/image";
import Link from "next/link";
import { Bell, Menu, Plus, Search, Sparkles } from "lucide-react";
import { useState } from "react";

import BackendStatusPill from "@/components/navigation/BackendStatusPill";
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
        {/* Left: Logo & Brand, plus desktop navigation links */}
        <div className="flex min-w-0 items-center gap-3 lg:gap-8">
          <Link href="/" className="flex shrink-0 items-center gap-2.5 sm:gap-3">
            <Image
              src="/consult-america-logo.jpg"
              alt="Consult America"
              width={36}
              height={36}
              className="h-8 w-8 rounded-full object-contain bg-white sm:h-9 sm:w-9"
              priority
            />
            <div className="min-w-0">
              <p className="truncate text-xs font-bold uppercase tracking-wide text-text-on-dark sm:text-sm">
                Consult America
              </p>
              <p className="truncate text-[11px] text-sirion-teal-soft sm:text-xs">
                Data Agent
              </p>
            </div>
          </Link>

          {/* Desktop mega menu dropdowns (lg+ only) */}
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

        {/* Right side: Desktop actions (lg+ only) */}
        <div className="hidden items-center gap-3 lg:flex">
          <Link href="/extraction/new" className="btn-new-extraction">
            <Plus className="h-4 w-4 shrink-0" strokeWidth={2} />
            <span className="whitespace-nowrap">New Extraction</span>
          </Link>

          <Link href="/ask" className="btn-ask-agent">
            <Sparkles className="h-4 w-4 shrink-0" strokeWidth={1.75} />
            <span className="whitespace-nowrap">Ask Data Agent</span>
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

          <div className="flex items-center gap-3 border-l border-white/10 pl-3">
            <BackendStatusPill />
            <Image
              src="/consult-america-logo.jpg"
              alt="Consult America"
              width={32}
              height={32}
              className="h-8 w-8 rounded-full object-contain bg-white"
            />
          </div>
        </div>

        {/* Right side: Mobile & Tablet triggers (<lg only) */}
        <div className="flex items-center gap-1.5 sm:gap-2 lg:hidden">
          <BackendStatusPill />

          <button
            type="button"
            onClick={onOpenSearch}
            aria-label="Search"
            className="nav-icon-button"
          >
            <Search className="h-4 w-4" strokeWidth={1.75} />
          </button>

          <button
            type="button"
            aria-label="Notifications"
            className="nav-icon-button"
          >
            <Bell className="h-4 w-4" strokeWidth={1.75} />
          </button>

          <button
            type="button"
            className="nav-menu-button"
            aria-label="Open menu"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-4 w-4" strokeWidth={1.75} />
          </button>
        </div>
      </header>

      <MobileNavigation open={mobileOpen} onClose={() => setMobileOpen(false)} />
    </>
  );
}
