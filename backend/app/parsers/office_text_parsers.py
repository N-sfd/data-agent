"""Native parsers that feed the common DocumentPage model (no OCR)."""

from __future__ import annotations

import csv
import html
import re
from io import StringIO
from pathlib import Path


def parse_plain_text(file_path: str | Path) -> dict:
    path = Path(file_path)
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    paragraphs = [line for line in text.splitlines() if line.strip()]
    return {"paragraphs": paragraphs, "tables": [], "text": text}


def parse_csv_file(file_path: str | Path) -> dict:
    path = Path(file_path)
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.reader(StringIO(raw))
    rows = [list(row) for row in reader]
    paragraphs = [" | ".join(cell.strip() for cell in row) for row in rows]
    tables = [rows] if rows else []
    return {
        "paragraphs": paragraphs,
        "tables": tables,
        "text": "\n".join(paragraphs),
    }


def parse_html_file(file_path: str | Path) -> dict:
    path = Path(file_path)
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    # Lightweight strip — enough for ingest; intelligence uses plain text.
    no_script = re.sub(
        r"(?is)<(script|style)[^>]*>.*?</\1>",
        " ",
        raw,
    )
    text = re.sub(r"(?s)<[^>]+>", " ", no_script)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    paragraphs = [line for line in text.splitlines() if line.strip()]
    return {"paragraphs": paragraphs, "tables": [], "text": text}


def parse_rtf_file(file_path: str | Path) -> dict:
    path = Path(file_path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    # Strip common RTF control words / groups into readable text.
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"\s+", " ", text).strip()
    paragraphs = [text] if text else []
    return {"paragraphs": paragraphs, "tables": [], "text": text}


def parse_xlsx_sheets(file_path: str | Path) -> list[dict]:
    """Return one dict per sheet: name, paragraphs, tables, text."""

    from openpyxl import load_workbook

    workbook = load_workbook(
        filename=str(file_path),
        read_only=True,
        data_only=True,
    )
    sheets: list[dict] = []

    try:
        for sheet in workbook.worksheets:
            rows: list[list[str]] = []
            for row in sheet.iter_rows(values_only=True):
                cells = [
                    "" if cell is None else str(cell).strip()
                    for cell in row
                ]
                if any(cells):
                    rows.append(cells)

            paragraphs = [" | ".join(row) for row in rows]
            sheets.append(
                {
                    "name": sheet.title,
                    "paragraphs": paragraphs,
                    "tables": [rows] if rows else [],
                    "text": "\n".join(paragraphs),
                }
            )
    finally:
        workbook.close()

    return sheets


def parse_pptx_slides(file_path: str | Path) -> list[dict]:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    from app.services.embedded_image_ocr import ocr_image_bytes

    presentation = Presentation(str(file_path))
    slides: list[dict] = []

    for index, slide in enumerate(presentation.slides, start=1):
        paragraphs: list[str] = []
        ocr_snippets: list[str] = []
        for shape in slide.shapes:
            if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.PICTURE:
                try:
                    blob = shape.image.blob
                except Exception:
                    blob = None
                if blob:
                    text = ocr_image_bytes(blob)
                    if text:
                        ocr_snippets.append(text)
                        paragraphs.append(text)
                continue

            if not getattr(shape, "has_text_frame", False):
                continue
            for paragraph in shape.text_frame.paragraphs:
                line = "".join(run.text for run in paragraph.runs).strip()
                if line:
                    paragraphs.append(line)

            # Fallback when runs are empty but text exists.
            if shape.text_frame.text.strip():
                for line in shape.text_frame.text.splitlines():
                    stripped = line.strip()
                    if stripped and stripped not in paragraphs:
                        paragraphs.append(stripped)

        text = "\n".join(paragraphs)
        slides.append(
            {
                "name": f"Slide {index}",
                "paragraphs": paragraphs,
                "tables": [],
                "text": text,
                "ocr_used": bool(ocr_snippets),
                "ocr_snippets": ocr_snippets,
            }
        )

    return slides
