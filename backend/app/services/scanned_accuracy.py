"""Scanned-document accuracy orchestration (layout → consensus → review).

Keeps the deterministic-first pipeline: layout geometry and label rejection
run before AI. Never silently invents uncertain ID/date/amount characters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.document_page import DocumentPage
from app.services.candidate_consensus import (
    ConsensusResult,
    ExtractionCandidate,
    resolve_candidates,
)
from app.services.ocr_word_layer import OcrLayout, OcrLine, OcrWord
from app.services.scanned_form_layout import associate_label_value
from app.services.targeted_ocr import crop_and_ocr


def layout_from_json(payload: dict[str, Any] | None) -> OcrLayout | None:
    if not payload or not isinstance(payload, dict):
        return None
    raw_words = payload.get("words") or []
    words: list[OcrWord] = []
    for item in raw_words:
        try:
            words.append(
                OcrWord(
                    text=str(item.get("text") or ""),
                    conf=float(item.get("conf") or 0.0),
                    x0=float(item.get("x0") or 0.0),
                    y0=float(item.get("y0") or 0.0),
                    x1=float(item.get("x1") or 0.0),
                    y1=float(item.get("y1") or 0.0),
                    block_num=int(item.get("block_num") or 0),
                    line_num=int(item.get("line_num") or 0),
                    word_num=int(item.get("word_num") or 0),
                )
            )
        except (TypeError, ValueError):
            continue

    lines: list[OcrLine] = []
    for item in payload.get("lines") or []:
        try:
            embedded = item.get("words") or []
            line_words: list[OcrWord] = []
            for word_item in embedded:
                try:
                    line_words.append(
                        OcrWord(
                            text=str(word_item.get("text") or ""),
                            conf=float(word_item.get("conf") or 0.0),
                            x0=float(word_item.get("x0") or 0.0),
                            y0=float(word_item.get("y0") or 0.0),
                            x1=float(word_item.get("x1") or 0.0),
                            y1=float(word_item.get("y1") or 0.0),
                            block_num=int(word_item.get("block_num") or 0),
                            line_num=int(word_item.get("line_num") or 0),
                            word_num=int(word_item.get("word_num") or 0),
                        )
                    )
                except (TypeError, ValueError):
                    continue
            lines.append(
                OcrLine(
                    text=str(item.get("text") or ""),
                    conf=float(item.get("conf") or 0.0),
                    x0=float(item.get("x0") or 0.0),
                    y0=float(item.get("y0") or 0.0),
                    x1=float(item.get("x1") or 0.0),
                    y1=float(item.get("y1") or 0.0),
                    words=line_words,
                )
            )
        except (TypeError, ValueError):
            continue

    if not lines and words:
        grouped: dict[tuple[int, int], list[OcrWord]] = {}
        for word in words:
            grouped.setdefault((word.block_num, word.line_num), []).append(word)
        for key in sorted(grouped):
            line_words = sorted(grouped[key], key=lambda item: item.x0)
            confs = [item.conf for item in line_words]
            lines.append(
                OcrLine(
                    text=" ".join(item.text for item in line_words),
                    conf=sum(confs) / len(confs) if confs else 0.0,
                    x0=min(item.x0 for item in line_words),
                    y0=min(item.y0 for item in line_words),
                    x1=max(item.x1 for item in line_words),
                    y1=max(item.y1 for item in line_words),
                    words=line_words,
                )
            )

    mean = payload.get("mean_word_confidence")
    if mean is None and words:
        mean = sum(word.conf for word in words) / len(words)
    return OcrLayout(
        words=words,
        lines=lines,
        mean_word_confidence=float(mean) if mean is not None else None,
        engine=str(payload.get("engine") or "pytesseract_image_to_data"),
    )


def layout_candidates_for_target(
    *,
    page: DocumentPage,
    requested_label: str,
    value_type: str | None,
    known_labels: frozenset[str] | None,
) -> list[ExtractionCandidate]:
    layout = layout_from_json(getattr(page, "ocr_layout_json", None))
    if layout is None:
        return []
    hit = associate_label_value(
        layout,
        requested_label=requested_label,
        known_labels=known_labels,
        value_type=value_type,
    )
    if hit is None:
        return []
    ocr_conf = None
    if layout.mean_word_confidence is not None:
        ocr_conf = layout.mean_word_confidence
    return [
        ExtractionCandidate(
            value=hit.value,
            raw_ocr=hit.value,
            method=hit.method,
            ocr_confidence=ocr_conf,
            layout_confidence=hit.layout_confidence,
            source_page=page.page_number,
            source_bbox=list(hit.bbox),
        )
    ]


def maybe_targeted_second_pass(
    *,
    pdf_path: Path | None,
    page: DocumentPage,
    bbox: list[float] | None,
    language: str = "eng",
) -> ExtractionCandidate | None:
    """Crop+OCR a field region when the PDF is available locally."""

    if pdf_path is None or bbox is None or len(bbox) != 4:
        return None
    if not pdf_path.exists():
        return None
    try:
        import fitz
    except ImportError:
        return None

    try:
        with fitz.open(pdf_path) as document:
            if page.page_number < 1 or page.page_number > document.page_count:
                return None
            fitz_page = document.load_page(page.page_number - 1)
            # Modest render — crop itself upscales in targeted_ocr.
            pixmap = fitz_page.get_pixmap(dpi=200)
            image_bytes = pixmap.tobytes("png")
            result = crop_and_ocr(
                image_bytes,
                bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                page_width=float(page.page_width or fitz_page.rect.width),
                page_height=float(page.page_height or fitz_page.rect.height),
                language=language,
            )
    except Exception:
        return None

    text = (result.text or "").strip()
    if not text:
        return None
    # Prefer last token for multi-word OCR of a small ID cell.
    compact = text.split()[-1] if " " in text and len(text.split()[-1]) >= 6 else text
    return ExtractionCandidate(
        value=compact,
        raw_ocr=text,
        method=result.method,
        ocr_confidence=None,
        layout_confidence=0.75,
        source_page=page.page_number,
        source_bbox=list(bbox),
        notes=f"targeted_scale={result.scale:.2f}",
    )


def resolve_with_consensus(
    candidates: list[ExtractionCandidate],
    *,
    field_key: str,
    value_type: str | None,
    known_labels: frozenset[str] | None,
) -> ConsensusResult:
    return resolve_candidates(
        candidates,
        value_type=value_type,
        known_labels=known_labels,
    )
