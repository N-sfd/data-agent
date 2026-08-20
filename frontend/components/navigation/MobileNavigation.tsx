"use client";

import Link from "next/link";
import { X } from "lucide-react";

import MegaMenu from "@/components/navigation/MegaMenu";
import {
  GOVERNANCE_SECTIONS,
  INTELLIGENCE_SECTIONS,
  OVERVIEW_LINKS,
  PLATFORM_SECTIONS,
  REVIEW_SECTIONS,
} from "@/components/navigation/nav-config";

interface MobileNavigationProps {
  open: boolean;
  onClose: () => void;
}

export default function MobileNavigation({
  open,
  onClose,
}: MobileNavigationProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] lg:hidden">
      <button
        type="button"
        aria-label="Close navigation"
        className="absolute inset-0 bg-sirion-bg-deep/70 backdrop-blur-sm"
        onClick={onClose}
      />

      <aside className="absolute inset-y-0 left-0 flex w-[min(100%,360px)] flex-col bg-menu-background shadow-2xl">
        <div className="flex items-center justify-between border-b border-black/5 px-5 py-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-text-dark">
              Consult America
            </p>
            <p className="text-xs text-text-teal">Data Agent</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-text-dark hover:bg-menu-tile"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-4">
          <Link
            href="/extraction/new"
            onClick={onClose}
            className="btn-ask-agent w-full justify-center"
          >
            + New Extraction
          </Link>

          <Link href="/ask" onClick={onClose} className="btn-secondary w-full justify-center">
            Ask Data Agent
          </Link>

          <div className="space-y-4">
            <p className="px-1 text-xs font-semibold uppercase tracking-wider text-text-teal">
              Platform
            </p>
            <MegaMenu
              overviewTitle="Platform Overview"
              overviewLinks={OVERVIEW_LINKS}
              sections={PLATFORM_SECTIONS}
              onNavigate={onClose}
            />
          </div>

          <div className="space-y-4">
            <p className="px-1 text-xs font-semibold uppercase tracking-wider text-text-teal">
              Intelligence
            </p>
            <MegaMenu sections={INTELLIGENCE_SECTIONS} onNavigate={onClose} />
          </div>

          <div className="space-y-4">
            <p className="px-1 text-xs font-semibold uppercase tracking-wider text-text-teal">
              Review
            </p>
            <MegaMenu sections={REVIEW_SECTIONS} onNavigate={onClose} />
          </div>

          <div className="space-y-4">
            <p className="px-1 text-xs font-semibold uppercase tracking-wider text-text-teal">
              Governance
            </p>
            <MegaMenu sections={GOVERNANCE_SECTIONS} onNavigate={onClose} />
          </div>
        </div>
      </aside>
    </div>
  );
}
