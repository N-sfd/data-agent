"use client";

import { useEffect, useRef } from "react";

/** A small tri-state checkbox for grid selection (row, column, all). */
export default function SelectCheckbox({
  checked,
  indeterminate = false,
  onChange,
  label,
  className = "",
  small = false,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: () => void;
  label: string;
  className?: string;
  /** A cell's own checkbox: smaller than row / column checkboxes. */
  small?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate && !checked;
  }, [indeterminate, checked]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      onClick={(event) => event.stopPropagation()}
      aria-label={label}
      className={`${small ? "h-3 w-3" : "h-3.5 w-3.5"} shrink-0 cursor-pointer accent-[var(--primary)] align-middle ${className}`}
    />
  );
}
