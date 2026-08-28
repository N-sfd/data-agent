"use client";

import Image from "next/image";
import Link from "next/link";
import { Plus, Sparkles, X } from "lucide-react";

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
          <div className="flex min-w-0 items-center gap-3">
            <Image
              src="/consult-america-logo.jpg"
              alt="Consult America"
              width={36}
              height={36}
              className="h-9 w-9 shrink-0 rounded-full object-contain bg-white"
            />
            <div className="min-w-0">
              <p className="text-sm font-semibold uppercase tracking-wide text-text-dark">
                Consult America
              </p>
              <p className="text-xs text-text-teal">Data Agent</p>
            </div>
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

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          <div className="space-y-2.5 pb-2">
            <Link
              href="/extraction/new"
              onClick={onClose}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-black/10 bg-black/5 px-4 py-3 text-sm font-semibold text-text-dark transition hover:bg-black/10 dark:border-white/15 dark:bg-white/5 dark:text-white dark:hover:bg-white/10"
            >
              <Plus className="h-4 w-4 shrink-0" strokeWidth={2} />
              <span className="whitespace-nowrap">New Extraction</span>
            </Link>

            <Link
              href="/ask"
              onClick={onClose}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent-purple px-4 py-3 text-sm font-semibold text-white transition hover:bg-accent-purple-dark"
            >
              <Sparkles className="h-4 w-4 shrink-0" strokeWidth={1.75} />
              <span className="whitespace-nowrap">Ask Data Agent</span>
            </Link>
          </div>

          <div className="space-y-4 border-t border-black/5 pt-4">
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
