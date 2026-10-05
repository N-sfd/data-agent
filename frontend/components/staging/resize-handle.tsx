"use client";

import { useCallback, useState } from "react";

const MIN_COLUMN = 48;
const MAX_COLUMN = 1200;
const MIN_ROW = 24;
const MAX_ROW = 480;
/** One arrow-key press. */
const STEP = 16;

type Sizes = Readonly<Record<string, number>>;

function resized(sizes: Sizes, id: string, size: number | null, min: number, max: number): Sizes {
  const next = { ...sizes };
  if (size == null) delete next[id];
  else next[id] = Math.round(Math.min(max, Math.max(min, size)));
  return next;
}

/** Excel-style column widths and row heights a reader set by hand (outer
 * cell size, px). Absent = the grid's own automatic size. */
export function useGridSizes() {
  const [columns, setColumns] = useState<Sizes>({});
  const [rows, setRows] = useState<Sizes>({});
  const setColumn = useCallback(
    (id: string, size: number | null) => setColumns((current) => resized(current, id, size, MIN_COLUMN, MAX_COLUMN)),
    [],
  );
  const setRow = useCallback(
    (id: string, size: number | null) => setRows((current) => resized(current, id, size, MIN_ROW, MAX_ROW)),
    [],
  );
  return { columns, rows, setColumn, setRow };
}

/** The draggable edge of a column header (right) or a row (bottom): drag,
 * or focus it and use the arrow keys; double-click returns to auto size.
 * Its cell (or row) must be positioned (relative / sticky). */
export default function ResizeHandle({
  axis,
  label,
  onResize,
  onReset,
}: {
  axis: "column" | "row";
  label: string;
  onResize: (size: number) => void;
  onReset: () => void;
}) {
  const column = axis === "column";

  function measure(handle: Element): number {
    const box = (column ? handle.closest("th, td") : handle.closest("tr"))?.getBoundingClientRect();
    return box ? (column ? box.width : box.height) : 0;
  }

  function onPointerDown(event: React.PointerEvent<HTMLSpanElement>) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const handle = event.currentTarget;
    const start = column ? event.clientX : event.clientY;
    const base = measure(handle);
    handle.setPointerCapture(event.pointerId);
    const move = (next: PointerEvent) => onResize(base + (column ? next.clientX : next.clientY) - start);
    const end = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", end);
      handle.removeEventListener("pointercancel", end);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", end);
    handle.addEventListener("pointercancel", end);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLSpanElement>) {
    const grow = column ? "ArrowRight" : "ArrowDown";
    const shrink = column ? "ArrowLeft" : "ArrowUp";
    if (event.key !== grow && event.key !== shrink) return;
    event.preventDefault();
    event.stopPropagation();
    onResize(measure(event.currentTarget) + (event.key === grow ? STEP : -STEP));
  }

  return (
    <span
      role="separator"
      aria-orientation={column ? "vertical" : "horizontal"}
      aria-label={label}
      tabIndex={0}
      title={`Drag or use the arrow keys to resize the ${axis} · double-click to reset`}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
      onClick={(event) => event.stopPropagation()}
      onDoubleClick={(event) => {
        event.stopPropagation();
        onReset();
      }}
      className={`grid-resize grid-resize-${axis}`}
    />
  );
}
