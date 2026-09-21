"""Word/line OCR layer with bounding boxes and per-token confidence.

This is additive to MuPDF page text. Callers keep `final_text` from the
stable MuPDF/pytesseract string path and optionally persist this richer
geometry for layout association and targeted second-pass OCR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any


@dataclass(frozen=True)
class OcrWord:
    text: str
    conf: float
    x0: float
    y0: float
    x1: float
    y1: float
    block_num: int
    line_num: int
    word_num: int


@dataclass(frozen=True)
class OcrLine:
    text: str
    conf: float
    x0: float
    y0: float
    x1: float
    y1: float
    words: list[OcrWord]


@dataclass(frozen=True)
class OcrLayout:
    words: list[OcrWord]
    lines: list[OcrLine]
    mean_word_confidence: float | None
    engine: str = "pytesseract_image_to_data"

    def to_json(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "mean_word_confidence": self.mean_word_confidence,
            "words": [asdict(word) for word in self.words],
            "lines": [
                {
                    "text": line.text,
                    "conf": line.conf,
                    "x0": line.x0,
                    "y0": line.y0,
                    "x1": line.x1,
                    "y1": line.y1,
                    "word_count": len(line.words),
                    "words": [asdict(word) for word in line.words],
                }
                for line in self.lines
            ],
        }


def extract_ocr_layout(
    image_bytes: bytes,
    *,
    language: str = "eng",
    timeout_seconds: int = 45,
) -> OcrLayout | None:
    """Run pytesseract image_to_data and rebuild words/lines with geometry."""

    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return None

    from app.services.embedded_image_ocr import _configure_pytesseract

    _configure_pytesseract()

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            rgb = image.convert("RGB")
            data = pytesseract.image_to_data(
                rgb,
                lang=language,
                timeout=timeout_seconds,
                output_type=pytesseract.Output.DICT,
            )
    except Exception:
        return None

    words: list[OcrWord] = []
    n = len(data.get("text") or [])
    for index in range(n):
        text = str(data["text"][index] or "").strip()
        if not text:
            continue
        try:
            conf_raw = float(data["conf"][index])
        except (TypeError, ValueError):
            conf_raw = -1.0
        if conf_raw < 0:
            continue
        x = float(data["left"][index])
        y = float(data["top"][index])
        w = float(data["width"][index])
        h = float(data["height"][index])
        words.append(
            OcrWord(
                text=text,
                conf=conf_raw / 100.0,
                x0=x,
                y0=y,
                x1=x + w,
                y1=y + h,
                block_num=int(data["block_num"][index]),
                line_num=int(data["line_num"][index]),
                word_num=int(data["word_num"][index]),
            )
        )

    lines_map: dict[tuple[int, int], list[OcrWord]] = {}
    for word in words:
        key = (word.block_num, word.line_num)
        lines_map.setdefault(key, []).append(word)

    lines: list[OcrLine] = []
    for key in sorted(lines_map):
        line_words = sorted(lines_map[key], key=lambda item: item.x0)
        text = " ".join(item.text for item in line_words)
        confs = [item.conf for item in line_words]
        lines.append(
            OcrLine(
                text=text,
                conf=sum(confs) / len(confs) if confs else 0.0,
                x0=min(item.x0 for item in line_words),
                y0=min(item.y0 for item in line_words),
                x1=max(item.x1 for item in line_words),
                y1=max(item.y1 for item in line_words),
                words=line_words,
            )
        )

    mean = (
        sum(word.conf for word in words) / len(words) if words else None
    )
    return OcrLayout(words=words, lines=lines, mean_word_confidence=mean)
