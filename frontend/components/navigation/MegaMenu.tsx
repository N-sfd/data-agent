"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";

import type { MegaMenuSection } from "@/components/navigation/nav-config";

interface MegaMenuProps {
  overviewTitle?: string;
  overviewLinks?: { label: string; href: string; icon: LucideIcon }[];
  sections: MegaMenuSection[];
  onNavigate?: () => void;
}

export default function MegaMenu({
  overviewTitle = "Overview",
  overviewLinks = [],
  sections,
  onNavigate,
}: MegaMenuProps) {
  return (
    <div className="mega-menu-panel animate-fade-in">
      <div className="grid gap-8 lg:grid-cols-[minmax(180px,220px)_1fr]">
        {overviewLinks.length > 0 && (
          <div className="space-y-4">
            <p className="mega-menu-section-title">{overviewTitle}</p>
            <div className="space-y-2">
              {overviewLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={onNavigate}
                  className="group flex items-center gap-2 text-sm font-medium text-text-dark hover:text-sirion-teal"
                >
                  <link.icon className="h-4 w-4 text-sirion-teal" strokeWidth={1.75} />
                  {link.label}
                  <ArrowRight className="ml-auto h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
                </Link>
              ))}
            </div>
          </div>
        )}

        <div
          className={[
            "grid gap-6",
            sections.length >= 2 ? "sm:grid-cols-2" : "grid-cols-1",
          ].join(" ")}
        >
          {sections.map((section) => (
            <div key={section.title}>
              <p className="mega-menu-section-title">{section.title}</p>
              <div className="mt-3 grid gap-2">
                {section.tiles.map((tile) => (
                  <Link
                    key={`${section.title}-${tile.href}-${tile.label}`}
                    href={tile.href}
                    onClick={onNavigate}
                    className="mega-menu-tile group"
                  >
                    <tile.icon
                      className="h-5 w-5 shrink-0 text-sirion-teal"
                      strokeWidth={1.75}
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-text-dark">
                        {tile.label}
                      </p>
                      {tile.description && (
                        <p className="mt-0.5 text-xs leading-5 text-text-teal">
                          {tile.description}
                        </p>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
