"""Layout-geometry form association for scanned pages.

Associates labels with values using spatial relationships (right / below /
same-ish row) over OCR word/line boxes — not flattened text proximity alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.generic_label_extractor import LayoutBlock, normalize_label
from app.services.label_rejection import looks_like_form_label, reject_as_field_value
from app.services.ocr_word_layer import OcrLayout, OcrLine


@dataclass(frozen=True)
class LayoutFormHit:
    label: str
    value: str
    bbox: list[float]
    label_bbox: list[float]
    layout_confidence: float
    method: str = "layout_form_cell"


def lines_to_blocks(layout: OcrLayout) -> list[LayoutBlock]:
    return [
        LayoutBlock(
            text=line.text,
            x0=line.x0,
            y0=line.y0,
            x1=line.x1,
            y1=line.y1,
        )
        for line in layout.lines
        if line.text.strip()
    ]


def _line_mean_conf(line: OcrLine) -> float:
    if not line.words:
        return line.conf
    return sum(word.conf for word in line.words) / len(line.words)


def associate_label_value(
    layout: OcrLayout,
    *,
    requested_label: str,
    known_labels: frozenset[str] | None = None,
    value_type: str | None = None,
) -> LayoutFormHit | None:
    """Find label line, then take nearest right/below non-label value."""

    label_norm = normalize_label(requested_label).lower()
    if not label_norm or not layout.lines:
        return None

    label_line: OcrLine | None = None
    for line in layout.lines:
        text_norm = normalize_label(line.text).lower()
        if label_norm in text_norm or text_norm in label_norm:
            # Prefer nearly-bare label cells over "Label: value" mashups
            # when a dedicated value cell exists nearby.
            label_line = line
            remainder = text_norm.replace(label_norm, "", 1).strip(" \t:#.-")
            if not remainder or looks_like_form_label(remainder):
                break

    if label_line is None:
        return None

    # Inline "Label: value" on the same line.
    remainder = normalize_label(label_line.text)
    for sep in (":", "#", "-", "."):
        if sep in remainder:
            left, right = remainder.split(sep, 1)
            if label_norm in left.lower() and right.strip():
                value = right.strip()
                if not reject_as_field_value(
                    value, value_type=value_type, known_labels=known_labels
                ):
                    return LayoutFormHit(
                        label=requested_label,
                        value=value,
                        bbox=[
                            label_line.x0,
                            label_line.y0,
                            label_line.x1,
                            label_line.y1,
                        ],
                        label_bbox=[
                            label_line.x0,
                            label_line.y0,
                            label_line.x1,
                            label_line.y1,
                        ],
                        layout_confidence=min(0.95, 0.55 + _line_mean_conf(label_line) * 0.4),
                        method="layout_inline_same_line",
                    )

    label_height = max(label_line.y1 - label_line.y0, 1.0)
    label_mid_y = (label_line.y0 + label_line.y1) / 2
    same_row: list[OcrLine] = []
    below: list[OcrLine] = []
    for line in layout.lines:
        if line is label_line or not line.text.strip():
            continue
        mid_y = (line.y0 + line.y1) / 2
        if abs(mid_y - label_mid_y) <= label_height * 1.2 and line.x0 > label_line.x1:
            same_row.append(line)
        elif (
            line.y0 >= label_line.y1 - 2
            and line.y0 - label_line.y1 <= label_height * 3.5
            and abs(line.x0 - label_line.x0) <= max(label_line.x1 - label_line.x0, 80) * 2
        ):
            below.append(line)

    same_row.sort(key=lambda item: item.x0)
    below.sort(key=lambda item: (item.y0, item.x0))

    for candidate in same_row + below:
        value = candidate.text.strip()
        if reject_as_field_value(
            value, value_type=value_type, known_labels=known_labels
        ):
            continue
        if looks_like_form_label(value):
            continue
        relation = "right" if candidate in same_row else "below"
        conf = min(
            0.96,
            0.50
            + _line_mean_conf(candidate) * 0.35
            + (0.12 if relation == "right" else 0.08),
        )
        return LayoutFormHit(
            label=requested_label,
            value=value,
            bbox=[candidate.x0, candidate.y0, candidate.x1, candidate.y1],
            label_bbox=[
                label_line.x0,
                label_line.y0,
                label_line.x1,
                label_line.y1,
            ],
            layout_confidence=conf,
            method=f"layout_form_cell_{relation}",
        )

    return None


def reconstruct_table_from_lines(
    layout: OcrLayout,
    *,
    min_rows: int = 2,
) -> dict | None:
    """Best-effort table reconstruction from vertically aligned OCR lines.

    Groups lines into rows by Y proximity and splits columns on large X gaps.
    Returns None when geometry is too weak — never invents a table.
    """

    if len(layout.lines) < min_rows:
        return None

    # Cluster into rows.
    sorted_lines = sorted(layout.lines, key=lambda line: line.y0)
    rows: list[list[OcrLine]] = []
    current: list[OcrLine] = []
    current_y: float | None = None
    for line in sorted_lines:
        if current_y is None or abs(line.y0 - current_y) <= 12:
            current.append(line)
            current_y = line.y0 if current_y is None else (current_y + line.y0) / 2
        else:
            rows.append(current)
            current = [line]
            current_y = line.y0
    if current:
        rows.append(current)

    if len(rows) < min_rows:
        return None

    def split_row(row_lines: list[OcrLine]) -> list[str]:
        words = sorted(
            (word for line in row_lines for word in line.words),
            key=lambda item: item.x0,
        )
        if not words:
            return [" ".join(line.text for line in row_lines)]
        cells: list[str] = []
        bucket = [words[0].text]
        prev_x1 = words[0].x1
        for word in words[1:]:
            gap = word.x0 - prev_x1
            if gap > 28:
                cells.append(" ".join(bucket))
                bucket = [word.text]
            else:
                bucket.append(word.text)
            prev_x1 = word.x1
        if bucket:
            cells.append(" ".join(bucket))
        return cells

    matrix = [split_row(row) for row in rows]
    col_count = max((len(row) for row in matrix), default=0)
    if col_count < 2:
        return None
    # Normalize ragged rows.
    normalized = [row + [""] * (col_count - len(row)) for row in matrix]
    headers = [
        cell.strip() or f"column_{index + 1}"
        for index, cell in enumerate(normalized[0])
    ]
    body = []
    for row in normalized[1:]:
        mapped = {
            headers[index]: row[index]
            for index in range(col_count)
        }
        if any(str(value).strip() for value in mapped.values()):
            body.append(mapped)
    if not body:
        return None
    return {
        "headers": headers,
        "rows": body,
        "source": "ocr_layout_coordinates",
        "row_count": len(body),
        "column_count": col_count,
    }
