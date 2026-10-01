"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import MegaMenu from "@/components/navigation/MegaMenu";
import type { MegaMenuSection } from "@/components/navigation/nav-config";

const CLOSE_DELAY_MS = 200;

interface NavDropdownProps {
  label: string;
  /** Hub page the label itself opens; the chevron opens the menu. */
  href?: string;
  sections: MegaMenuSection[];
  overviewTitle?: string;
  overviewLinks?: { label: string; href: string; icon: import("lucide-react").LucideIcon }[];
}

export default function NavDropdown({
  label,
  href,
  sections,
  overviewTitle,
  overviewLinks,
}: NavDropdownProps) {
  const [open, setOpen] = useState(false);
  // The header nav clips overflow (so items never collide with the action
  // buttons); the panel is therefore fixed-positioned under its button.
  const [anchor, setAnchor] = useState<{ top: number; left: number } | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const current = Boolean(
    href && (pathname === href.split("?")[0] || sections.some((section) => section.tiles.some((tile) => tile.href.split(/[?#]/)[0] === pathname && pathname !== "/"))),
  );

  const clearCloseTimer = useCallback(() => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }, []);

  const scheduleClose = useCallback(() => {
    clearCloseTimer();
    closeTimer.current = setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  }, [clearCloseTimer]);

  const place = useCallback(() => {
    const box = containerRef.current?.getBoundingClientRect();
    if (!box) return;
    const width = Math.min(720, window.innerWidth - 32);
    setAnchor({ top: box.bottom + 10, left: Math.max(16, Math.min(box.left, window.innerWidth - width - 16)) });
  }, []);

  const handleOpen = useCallback(() => {
    clearCloseTimer();
    place();
    setOpen(true);
  }, [clearCloseTimer, place]);

  // A mouse reaching the button has already opened the menu on hover, so
  // a mouse click keeps it open; keyboard activation (detail 0) toggles.
  const handleToggle = useCallback(
    (event: React.MouseEvent) => {
      clearCloseTimer();
      place();
      if (event.detail === 0) setOpen((current) => !current);
      else setOpen(true);
    },
    [clearCloseTimer, place],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    return () => clearCloseTimer();
  }, [clearCloseTimer]);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("resize", close);
    return () => window.removeEventListener("resize", close);
  }, [open]);

  return (
    <div
      ref={containerRef}
      className="relative"
      onMouseEnter={handleOpen}
      onMouseLeave={scheduleClose}
    >
      {href ? (
        <div
          className={[
            "nav-menu-button nav-menu-split",
            open || current ? "nav-menu-button-active" : "",
          ].join(" ")}
        >
          <Link
            href={href}
            onClick={() => setOpen(false)}
            aria-current={current ? "page" : undefined}
            className="nav-menu-split-link"
          >
            {label}
          </Link>
          <button
            type="button"
            aria-expanded={open}
            aria-haspopup="true"
            aria-label={`${label} menu`}
            onClick={handleToggle}
            className="nav-menu-split-toggle"
          >
            <ChevronDown
              className={["h-3.5 w-3.5 transition duration-200", open ? "rotate-180" : ""].join(" ")}
              strokeWidth={2}
            />
          </button>
        </div>
      ) : (
        <button
          type="button"
          aria-expanded={open}
          aria-haspopup="true"
          onClick={handleToggle}
          className={[
            "nav-menu-button",
            open ? "nav-menu-button-active" : "",
          ].join(" ")}
        >
          {label}
          <ChevronDown
            className={[
              "h-3.5 w-3.5 transition duration-200",
              open ? "rotate-180" : "",
            ].join(" ")}
            strokeWidth={2}
          />
        </button>
      )}

      {open && anchor && (
        <div
          className="fixed z-50 w-[min(720px,calc(100vw-2rem))]"
          style={{ top: anchor.top, left: anchor.left }}
          onMouseEnter={handleOpen}
          onMouseLeave={scheduleClose}
        >
          <MegaMenu
            overviewTitle={overviewTitle}
            overviewLinks={overviewLinks}
            sections={sections}
            onNavigate={() => setOpen(false)}
          />
        </div>
      )}
    </div>
  );
}
