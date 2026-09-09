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
      <header className="global-header app-header shrink-0">
        {/* Brand — never shrink */}
        <div className="header-left">
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
        </div>

        {/* Primary nav — can shrink; secondary items collapse first */}
        <nav className="header-nav" aria-label="Main navigation">
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
          <div className="header-nav-secondary">
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
          </div>
          <div className="header-nav-more">
            <NavDropdown
              label="More"
              overviewTitle="More"
              sections={[...REVIEW_SECTIONS, ...GOVERNANCE_SECTIONS]}
            />
          </div>
        </nav>

        {/* Actions — never shrink, never wrap onto nav */}
        <div className="header-actions">
          <Link href="/extraction/new" className="btn-new-extraction shrink-0">
            <Plus className="h-4 w-4 shrink-0" strokeWidth={2} />
            <span className="whitespace-nowrap">New Extraction</span>
          </Link>

          <Link href="/ask" className="btn-ask-agent shrink-0">
            <Sparkles className="h-4 w-4 shrink-0" strokeWidth={1.75} />
            <span className="whitespace-nowrap">Ask Data Agent</span>
          </Link>

          <button
            type="button"
            onClick={onOpenSearch}
            aria-label="Search"
            className="nav-icon-button shrink-0"
          >
            <Search className="h-4 w-4" strokeWidth={1.75} />
          </button>

          <button
            type="button"
            aria-label="Notifications"
            className="nav-icon-button shrink-0"
          >
            <Bell className="h-4 w-4" strokeWidth={1.75} />
          </button>

          <div className="flex shrink-0 items-center gap-3 border-l border-white/10 pl-3">
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

        {/* Mobile / tablet triggers */}
        <div className="header-mobile-triggers">
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
