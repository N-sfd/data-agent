"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import MegaMenu from "@/components/navigation/MegaMenu";
import type { MegaMenuSection } from "@/components/navigation/nav-config";

const CLOSE_DELAY_MS = 200;

interface NavDropdownProps {
  label: string;
  sections: MegaMenuSection[];
  overviewTitle?: string;
  overviewLinks?: { label: string; href: string; icon: import("lucide-react").LucideIcon }[];
}

export default function NavDropdown({
  label,
  sections,
  overviewTitle,
  overviewLinks,
}: NavDropdownProps) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

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

  const handleOpen = useCallback(() => {
    clearCloseTimer();
    setOpen(true);
  }, [clearCloseTimer]);

  const handleToggle = useCallback(() => {
    clearCloseTimer();
    setOpen((current) => !current);
  }, [clearCloseTimer]);

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

  return (
    <div
      ref={containerRef}
      className="relative"
      onMouseEnter={handleOpen}
      onMouseLeave={scheduleClose}
    >
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

      {open && (
        <div
          className="absolute left-0 top-[calc(100%+10px)] z-50 min-w-[min(720px,calc(100vw-2rem))]"
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
