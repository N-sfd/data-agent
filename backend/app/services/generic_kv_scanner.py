import re
from dataclasses import dataclass
from typing import Literal

from app.models.document_page import DocumentPage
from app.services.request_interpreter import STOP_WORDS

MAX_PAIRS_PER_PAGE = 40

ScanMethod = Literal[
    "form_field",
    "table_2col",
    "inline_regex",
    "stacked_line",
]


# NOTE: every gap/leading/trailing whitespace token below uses [ \t]
# (horizontal whitespace only), never the bare \s class. \s matches \n in
# Python's re module, so a bare \s{2,} "gap" would happily span a blank
# line and glue one line's label to a value two lines down — these
# patterns are all meant to stay within a single line.

_INLINE_LABEL_VALUE = re.compile(
    r"^[ \t]*([A-Z][A-Za-z0-9 /#.'\-]{2,40}?)[ \t]*[:.]{1,3}[ \t]*(\S.{0,120})[ \t]*$",
    re.MULTILINE,
)

# Many government-form labels (NAICS, PSC CD, DATE ISSUED, TYPE OF
# SOLICITATION, ...) carry no trailing punctuation at all — the label and
# its value are separated only by a wide column gap. An all-caps label
# requirement plus a 2+ space gap distinguishes this from ordinary prose
# (single-space word separation).
_INLINE_LABEL_VALUE_WIDE_GAP = re.compile(
    r"^[ \t]*([A-Z][A-Z0-9 /#.'\-]{1,40})[ \t]{2,}(\S.{0,120})[ \t]*$",
    re.MULTILINE,
)

_DOT_LEADER = re.compile(
    r"^[ \t]*([A-Za-z][A-Za-z0-9 /#'\-]{2,40}?)[ \t]*\.{4,}[ \t]*(\S.{0,80})[ \t]*$",
    re.MULTILINE,
)

# A label-only line must not itself contain a wide column gap (2+ spaces
# followed by more text) — that pattern is a same-line "LABEL   VALUE"
# form field (already handled by _INLINE_LABEL_VALUE), not a genuine
# label-on-its-own-line layout. Without this guard, wide-column forms get
# mis-parsed: the whole "LABEL   VALUE" line becomes the "label" and the
# next, unrelated line becomes the "value".
_STACKED_LABEL = re.compile(
    r"^(?!.*[ \t]{2,}\S)([A-Z][A-Z0-9 /#.'\-]{2,40})\n(?!\s*$)([^\n]{1,120})$",
    re.MULTILINE,
)

_ALL_CAPS = re.compile(r"^[A-Z0-9 /#.'\-]+$")

_NUMERIC_ONLY = re.compile(r"^[\s\d.,$%()-]+$")


@dataclass(frozen=True)
class ScannedPair:
    raw_label: str
    normalized_label: str
    value: str
    method: ScanMethod
    confidence: float


def _normalize_label(label: str) -> str:
    normalized = " ".join(label.strip().lower().split())
    return normalized.rstrip(".:-").strip()


def _looks_like_noise(label: str) -> bool:
    normalized = _normalize_label(label)
    if not normalized:
        return True
    words = normalized.split()
    if all(word in STOP_WORDS for word in words):
        return True
    return False


def _scan_form_fields(page: DocumentPage) -> list[ScannedPair]:
    pairs: list[ScannedPair] = []
    for raw_label, value in (page.form_fields_json or {}).items():
        if not value or not str(value).strip():
            continue
        pairs.append(
            ScannedPair(
                raw_label=str(raw_label).strip(),
                normalized_label=_normalize_label(str(raw_label)),
                value=str(value).strip(),
                method="form_field",
                confidence=0.95,
            )
        )
    return pairs


def _scan_two_column_tables(page: DocumentPage) -> list[ScannedPair]:
    pairs: list[ScannedPair] = []
    for table in page.tables_json or []:
        headers = [str(h) for h in (table.get("headers") or [])]
        if len(headers) != 2:
            continue
        for row in table.get("rows") or []:
            if isinstance(row, dict):
                values = list(row.values())
            elif isinstance(row, (list, tuple)):
                values = list(row)
            else:
                continue
            if len(values) != 2:
                continue
            label, value = str(values[0]).strip(), str(values[1]).strip()
            if not label or not value:
                continue
            if _NUMERIC_ONLY.match(label):
                continue
            pairs.append(
                ScannedPair(
                    raw_label=label,
                    normalized_label=_normalize_label(label),
                    value=value,
                    method="table_2col",
                    confidence=0.85,
                )
            )
    return pairs


_INLINE_PATTERNS: tuple[tuple[re.Pattern[str], float], ...] = (
    (_INLINE_LABEL_VALUE, 0.78),
    (_INLINE_LABEL_VALUE_WIDE_GAP, 0.8),
    (_DOT_LEADER, 0.76),
)


def _scan_inline_regex(text: str) -> list[ScannedPair]:
    pairs: list[ScannedPair] = []
    for pattern, confidence in _INLINE_PATTERNS:
        for match in pattern.finditer(text):
            label, value = match.group(1).strip(), match.group(2).strip()
            if not label or not value or _looks_like_noise(label):
                continue
            # All-caps government form labels (SOLICITATION NO., DODAAC, ...)
            # are high-signal — keep them above the primary detection floor.
            boosted = confidence
            if _ALL_CAPS.match(label):
                boosted = max(confidence, 0.82)
            pairs.append(
                ScannedPair(
                    raw_label=label,
                    normalized_label=_normalize_label(label),
                    value=value,
                    method="inline_regex",
                    confidence=boosted,
                )
            )
    return pairs


def _scan_stacked_lines(text: str) -> list[ScannedPair]:
    pairs: list[ScannedPair] = []
    for match in _STACKED_LABEL.finditer(text):
        label, value = match.group(1).strip(), match.group(2).strip()
        if not label or not value or _looks_like_noise(label):
            continue
        if _ALL_CAPS.match(value):
            continue
        pairs.append(
            ScannedPair(
                raw_label=label,
                normalized_label=_normalize_label(label),
                value=value,
                method="stacked_line",
                # All-caps stacked labels are common on SF/OF forms —
                # keep them at/above the primary detection floor (0.75).
                confidence=0.82 if _ALL_CAPS.match(label) else 0.62,
            )
        )
    return pairs


def scan_page_for_labeled_pairs(
    *,
    page: DocumentPage,
) -> list[ScannedPair]:
    text = page.final_text or ""

    all_pairs = (
        _scan_form_fields(page)
        + _scan_two_column_tables(page)
        + _scan_inline_regex(text)
        + _scan_stacked_lines(text)
    )

    best_by_label: dict[str, ScannedPair] = {}
    for pair in all_pairs:
        existing = best_by_label.get(pair.normalized_label)
        if existing is None or pair.confidence > existing.confidence:
            best_by_label[pair.normalized_label] = pair

    ranked = sorted(
        best_by_label.values(),
        key=lambda pair: pair.confidence,
        reverse=True,
    )

    return ranked[:MAX_PAIRS_PER_PAGE]
