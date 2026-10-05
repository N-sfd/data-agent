import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ResizeHandle, { useGridSizes } from "@/components/staging/resize-handle";

function Grid() {
  const sizes = useGridSizes();
  return (
    <table>
      <thead>
        <tr>
          <th style={sizes.columns.title ? { width: sizes.columns.title } : undefined} data-testid="title">
            Course Title
            <ResizeHandle
              axis="column"
              label="Resize column Course Title"
              onResize={(size) => sizes.setColumn("title", size)}
              onReset={() => sizes.setColumn("title", null)}
            />
          </th>
        </tr>
      </thead>
      <tbody>
        <tr style={sizes.rows.r1 ? { height: sizes.rows.r1 } : undefined} data-testid="row">
          <td>
            Company Law
            <ResizeHandle
              axis="row"
              label="Resize row Company Law"
              onResize={(size) => sizes.setRow("r1", size)}
              onReset={() => sizes.setRow("r1", null)}
            />
          </td>
        </tr>
      </tbody>
    </table>
  );
}

function measured(element: HTMLElement, width: number, height: number) {
  element.getBoundingClientRect = () => ({ width, height, top: 0, left: 0, right: width, bottom: height, x: 0, y: 0, toJSON: () => ({}) });
}

describe("ResizeHandle", () => {
  it("widens and narrows a column with the arrow keys and resets on double-click", () => {
    render(<Grid />);
    const header = screen.getByTestId("title");
    measured(header, 200, 40);
    const handle = screen.getByRole("separator", { name: "Resize column Course Title" });

    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(header.style.width).toBe("216px");
    measured(header, 216, 40);
    fireEvent.keyDown(handle, { key: "ArrowLeft" });
    expect(header.style.width).toBe("200px");

    fireEvent.doubleClick(handle);
    expect(header.style.width).toBe("");
  });

  it("makes a row taller with ArrowDown, never below the minimum", () => {
    render(<Grid />);
    const row = screen.getByTestId("row");
    measured(row, 300, 44);
    const handle = screen.getByRole("separator", { name: "Resize row Company Law" });

    fireEvent.keyDown(handle, { key: "ArrowDown" });
    expect(row.style.height).toBe("60px");
    measured(row, 300, 10);
    fireEvent.keyDown(handle, { key: "ArrowUp" });
    expect(row.style.height).toBe("24px");
  });
});
