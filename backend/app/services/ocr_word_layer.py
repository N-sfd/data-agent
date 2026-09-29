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
    # Two OCR passes read different text at this spot (fuse_layouts); the
    # reading is unresolved and must not be Verified.
    contested: bool = False


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

    from app.core.observability import log_event

    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        log_event("ocr_word_layout", stage="rendering_ocr", status="unavailable", error_category="ImportError", error=str(exc)[:300])
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
    except Exception as exc:
        # The page keeps its OCR text but loses positions — never silently.
        log_event(
            "ocr_word_layout",
            stage="rendering_ocr",
            status="error",
            error_category=type(exc).__name__,
            error=str(exc)[:500],
        )
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


def layout_from_textpage_words(
    words: list[tuple],
    *,
    scale: float,
) -> OcrLayout | None:
    """Word layer from the words MuPDF's own OCR pass already produced
    (``page.get_text("words", textpage=ocr_textpage)``, PDF points), scaled
    into the same pixel space as the pytesseract layer. Used when the
    separate pytesseract pass fails — e.g. times out on a slow CPU — so the
    page keeps real word positions without a second OCR run.

    MuPDF reports no per-word confidence; it stays unknown (None) rather
    than invented.
    """

    ocr_words: list[OcrWord] = []
    for item in words:
        x0, y0, x1, y1, text, block_num, line_num, word_num = item[:8]
        text = str(text or "").strip()
        if not text:
            continue
        ocr_words.append(
            OcrWord(
                text=text,
                conf=None,  # type: ignore[arg-type] — unknown, not invented
                x0=float(x0) * scale,
                y0=float(y0) * scale,
                x1=float(x1) * scale,
                y1=float(y1) * scale,
                block_num=int(block_num),
                line_num=int(line_num),
                word_num=int(word_num),
            )
        )
    if not ocr_words:
        return None
    lines_map: dict[tuple[int, int], list[OcrWord]] = {}
    for word in ocr_words:
        lines_map.setdefault((word.block_num, word.line_num), []).append(word)
    lines = [
        OcrLine(
            text=" ".join(w.text for w in line_words),
            conf=None,  # type: ignore[arg-type]
            x0=min(w.x0 for w in line_words),
            y0=min(w.y0 for w in line_words),
            x1=max(w.x1 for w in line_words),
            y1=max(w.y1 for w in line_words),
            words=line_words,
        )
        for key in sorted(lines_map)
        for line_words in [sorted(lines_map[key], key=lambda w: w.x0)]
    ]
    return OcrLayout(words=ocr_words, lines=lines, mean_word_confidence=None, engine="mupdf_textpage")


def layout_score(layout: "OcrLayout | None") -> float:
    """Total confidence of real words (≥ 2 letters/digits) — how much a
    layout actually read, used to choose between OCR variants."""

    if layout is None:
        return 0.0
    return sum(
        (word.conf or 0.0)
        for word in layout.words
        if sum(ch.isalnum() for ch in word.text) >= 2
    )


def _overlap(a: OcrWord, b: OcrWord) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    inter = ix * iy
    smaller = min((a.x1 - a.x0) * (a.y1 - a.y0), (b.x1 - b.x0) * (b.y1 - b.y0)) or 1.0
    return inter / smaller


def _iou(a: OcrWord, b: OcrWord) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    inter = ix * iy
    union = (a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - inter
    return inter / union if union > 0 else 0.0


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def fuse_layouts(primary: OcrLayout, secondary: OcrLayout) -> OcrLayout:
    """Word-level fusion of two OCR readings of the same page image (same
    pixel space). Agreeing words keep the better reading; words only one
    pass found are added; where the passes DISAGREE on the same spot, the
    higher-confidence text is kept but its confidence drops to the lower
    of the two — a contested reading must never look certain."""

    fused: list[OcrWord] = []
    used: set[int] = set()
    for word in primary.words:
        # Same word = boxes of similar extent. When the passes split text
        # differently ("10-07-1986" vs "10 - 07 - 1986") nothing matches and
        # the primary tokenization is kept as is.
        match_index = None
        for index, other in enumerate(secondary.words):
            if index not in used and _iou(word, other) >= 0.6:
                match_index = index
                break
        if match_index is None:
            fused.append(word)
            continue
        used.add(match_index)
        other = secondary.words[match_index]
        best, worst = (word, other) if (word.conf or 0) >= (other.conf or 0) else (other, word)
        if _norm(word.text) == _norm(other.text):
            fused.append(best)
        else:
            fused.append(
                OcrWord(
                    text=best.text,
                    conf=min(word.conf or 0.0, other.conf or 0.0),
                    x0=best.x0, y0=best.y0, x1=best.x1, y1=best.y1,
                    block_num=best.block_num, line_num=best.line_num, word_num=best.word_num,
                    contested=True,
                )
            )
    # Words only the secondary pass read (e.g. digits hidden by a watermark
    # in the primary image) fill the gaps.
    for index, other in enumerate(secondary.words):
        if index not in used and not any(_overlap(other, word) >= 0.3 for word in fused):
            fused.append(other)

    lines_map: dict[tuple[int, int], list[OcrWord]] = {}
    for word in fused:
        # Line identity is geometric after fusion: words whose vertical
        # centres agree within half a word height share a line.
        centre = (word.y0 + word.y1) / 2
        height = max(1.0, word.y1 - word.y0)
        key = next(
            (k for k, ws in lines_map.items() if abs((ws[0].y0 + ws[0].y1) / 2 - centre) <= 0.5 * height),
            (len(lines_map), 0),
        )
        lines_map.setdefault(key, []).append(word)
    lines: list[OcrLine] = []
    for line_words in lines_map.values():
        line_words = sorted(line_words, key=lambda w: w.x0)
        confs = [w.conf for w in line_words if w.conf is not None]
        lines.append(
            OcrLine(
                text=" ".join(w.text for w in line_words),
                conf=sum(confs) / len(confs) if confs else 0.0,
                x0=min(w.x0 for w in line_words), y0=min(w.y0 for w in line_words),
                x1=max(w.x1 for w in line_words), y1=max(w.y1 for w in line_words),
                words=line_words,
            )
        )
    lines.sort(key=lambda line: (line.y0, line.x0))
    confs = [w.conf for w in fused if w.conf is not None]
    return OcrLayout(
        words=fused,
        lines=lines,
        mean_word_confidence=sum(confs) / len(confs) if confs else None,
        engine=f"{primary.engine}+fused",
    )
