"""Best-effort nearby-heading lookup, shared by extraction and export.

Finds the nearest numbered section heading ("6.2 Payment Terms", "SF33 /
Section A") preceding a matched value on the same page, so exported/
displayed fields can be grouped the way a reader would group them —
without ever fabricating a section when none is confidently found.
"""

from __future__ import annotations

import re

# Matches numbered heading lines like "6.2 Payment Terms",
# "Section 6.2 - Payment", or "6. Termination".
SECTION_HEADING_PATTERN = re.compile(
    r"^\s*(?:Section\s+)?(\d{1,2}(?:\.\d{1,2})?)\s*"
    r"[-–—.]?\s*"
    r"([A-Z][A-Za-z0-9 /&'\-]{2,60})\s*$",
    re.MULTILINE,
)


def find_nearby_section(text: str, value: str) -> str | None:
    """
    Best-effort: find the nearest numbered heading preceding the
    matched value on the same page. Returns None (never fabricated)
    when no heading is confidently found.
    """

    if not text or not value:
        return None

    offset = text.find(value)

    if offset == -1:
        return None

    preceding = text[:offset]

    matches = list(SECTION_HEADING_PATTERN.finditer(preceding))

    if not matches:
        return None

    match = matches[-1]
    number = match.group(1)
    title = match.group(2).strip()

    return f"Section {number} — {title}"
