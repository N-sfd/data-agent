"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import CompactMenu from "@/components/navigation/CompactMenu";
import type { MegaMenuSection } from "@/components/navigation/nav-config";

/** Only one header menu is open at a time: opening one tells the others. */
const OPEN_EVENT = "data-agent:nav-menu-open";
const PANEL_WIDTH = 680;

interface NavDropdownProps {
  label: string;
  /** The menu's hub page (linked inside the popover). */
  href?: string;
  sections: MegaMenuSection[];
  /** This menu owns the current page (one filled button at a time). */
  current?: boolean;
}

export default function NavDropdown({ label, href, sections, current = false }: NavDropdownProps) {
  const [open, setOpen] = useState(false);
  // The header nav clips overflow, so the popover is fixed-positioned under
  // its button and kept inside the viewport.
  const [anchor, setAnchor] = useState<{ top: number; left: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const pathname = usePathname();

  const close = useCallback((restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) buttonRef.current?.focus();
  }, []);

  const toggle = useCallback(() => {
    const box = containerRef.current?.getBoundingClientRect();
    if (box) {
      const width = Math.min(PANEL_WIDTH, window.innerWidth - 32);
      setAnchor({ top: box.bottom + 8, left: Math.max(16, Math.min(box.left, window.innerWidth - width - 16)) });
    }
    setOpen((value) => {
      if (!value) window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: menuId }));
      return !value;
    });
  }, [menuId]);

  // Close when another menu opens, on navigation, outside click, Esc, resize.
  useEffect(() => {
    function onOtherOpen(event: Event) {
      if ((event as CustomEvent<string>).detail !== menuId) setOpen(false);
    }
    window.addEventListener(OPEN_EVENT, onOtherOpen);
    return () => window.removeEventListener(OPEN_EVENT, onOtherOpen);
  }, [menuId]);

  // Navigation closes the menu (adjusting state during render, not in an effect).
  const [openedOn, setOpenedOn] = useState(pathname);
  if (openedOn !== pathname) {
    setOpenedOn(pathname);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    function onPointer(event: MouseEvent) {
      const target = event.target as Node;
      if (!containerRef.current?.contains(target) && !panelRef.current?.contains(target)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") close(true);
    }
    const onResize = () => setOpen(false);
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
    };
  }, [open, close]);

  function onButtonKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) toggle();
      requestAnimationFrame(() => panelRef.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus());
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={open ? menuId : undefined}
        onClick={toggle}
        onKeyDown={onButtonKeyDown}
        className={[
          "nav-menu-button",
          current ? "nav-menu-button-current" : "",
          open ? "nav-menu-button-open" : "",
        ].join(" ")}
      >
        {label}
        <ChevronDown
          aria-hidden="true"
          className={["h-3.5 w-3.5 transition-transform duration-200", open ? "rotate-180" : ""].join(" ")}
          strokeWidth={2}
        />
      </button>

      {open && anchor && (
        <div
          ref={panelRef}
          className="fixed z-50"
          style={{ top: anchor.top, left: anchor.left, width: `min(${PANEL_WIDTH}px, calc(100vw - 2rem))` }}
        >
          <CompactMenu id={menuId} label={label} sections={sections} overviewHref={href} onNavigate={() => close()} />
        </div>
      )}
    </div>
  );
}
