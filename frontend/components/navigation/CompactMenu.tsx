"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import type { MegaMenuSection } from "@/components/navigation/nav-config";

interface CompactMenuProps {
  id: string;
  label: string;
  sections: MegaMenuSection[];
  /** The menu's hub page, linked once at the foot of the popover. */
  overviewHref?: string;
  onNavigate: () => void;
}

/** A compact two-column navigation popover: small icon, title and one short
 * line per row. Two sections sit side by side; a single section flows into
 * two columns. */
export default function CompactMenu({ id, label, sections, overviewHref, onNavigate }: CompactMenuProps) {
  const columns = sections.length === 1
    ? splitInTwo(sections[0])
    : sections;
  return (
    <div id={id} role="menu" aria-label={`${label} menu`} className="compact-menu-panel">
      <div className={columns.length > 1 ? "grid gap-x-4 gap-y-3 sm:grid-cols-2" : "grid gap-3"}>
        {columns.map((section, index) => (
          <div key={`${section.title}-${index}`} className="min-w-0">
            {section.title && <p className="compact-menu-title">{section.title}</p>}
            <ul className="mt-1 space-y-0.5">
              {section.tiles.map((tile) => (
                <li key={`${tile.href}-${tile.label}`}>
                  <Link href={tile.href} role="menuitem" onClick={onNavigate} className="compact-menu-row group">
                    <tile.icon className="mt-0.5 h-4 w-4 shrink-0 text-sirion-teal" strokeWidth={1.75} aria-hidden="true" />
                    <span className="min-w-0">
                      <span className="block truncate text-[13px] font-medium text-text-dark group-hover:text-sirion-teal">
                        {tile.label}
                      </span>
                      {tile.description && (
                        <span className="block truncate text-xs text-text-secondary">{tile.description}</span>
                      )}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {overviewHref && (
        <div className="mt-2 border-t border-black/5 pt-2">
          <Link href={overviewHref} role="menuitem" onClick={onNavigate} className="compact-menu-overview group">
            {label} overview
            <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" aria-hidden="true" />
          </Link>
        </div>
      )}
    </div>
  );
}

function splitInTwo(section: MegaMenuSection): MegaMenuSection[] {
  if (section.tiles.length < 4) return [section];
  const half = Math.ceil(section.tiles.length / 2);
  return [
    { title: section.title, tiles: section.tiles.slice(0, half) },
    { title: "", tiles: section.tiles.slice(half) },
  ];
}
