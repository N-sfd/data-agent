"""Document structural outline: section/part/attachment boundaries.

Section detection runs as its own stage, ahead of field promotion and
export, so every consumer (dynamic target extraction, the FIELD_SPECS
pipeline, CSV/XLSX export, the API) resolves a field's section from the
same outline instead of each guessing independently from a single page's
text.

A federal contract's Uniform Contract Format (UCF) sections span many
pages — a value on page 26 with no heading of its own belongs to whatever
section most recently started, not to nothing. The previous
single-page-only lookup (section_detection.find_nearby_section) could
only ever succeed when a heading and a value shared literally the same
page, which is why "Section" read blank for nearly every field. This
module tracks boundaries across the whole document so a section carries
forward until superseded by the next one.

TOC pages are explicitly excluded from heading detection: a TOC lists
every heading up front, and treating those mentions as the *start* of
each section would place every field in the document under whatever
section happens to be closest to the TOC list, not where the field
actually lives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, Sequence

# Uniform Contract Format (UCF) sections, Parts I-IV. Federal solicitations/
# contracts overwhelmingly follow this structure regardless of agency, so
# this is a document-format signal, not something hardcoded to one contract.
UCF_SECTIONS: dict[str, str] = {
    "A": "Solicitation/Contract Form",
    "B": "Supplies or Services and Prices/Costs",
    "C": "Description/Specifications/Statement of Work",
    "D": "Packaging and Marking",
    "E": "Inspection and Acceptance",
    "F": "Deliveries or Performance",
    "G": "Contract Administration Data",
    "H": "Special Contract Requirements",
    "I": "Contract Clauses",
    "J": "List of Attachments",
    "K": "Representations, Certifications and Other Statements of Offerors",
    "L": "Instructions, Conditions and Notices to Offerors",
    "M": "Evaluation Factors for Award",
}

_UCF_TITLE_TO_CODE: dict[str, str] = {
    title.lower(): code for code, title in UCF_SECTIONS.items()
}

# "SECTION B", "SECTION B -", "SECTION B — SUPPLIES..." (title optional —
# the code alone is enough to anchor the boundary; the title is filled in
# from UCF_SECTIONS when the heading doesn't spell it out).
_SECTION_MARKER = re.compile(
    r"^\s*SECTION\s+([A-M])\b[\s.:\-–—]*([A-Z][A-Za-z0-9 /,&'\-]{0,80})?\s*$",
    re.MULTILINE,
)
# A known UCF title appearing on its own line, without a leading
# "SECTION X" marker (common right under a "SECTION X" line, or as the
# only heading text when the form omits the letter).
_KNOWN_TITLE_LINE = re.compile(
    r"^\s*(" + "|".join(re.escape(t.upper()) for t in UCF_SECTIONS.values()) + r")\s*$",
    re.MULTILINE,
)
_PART_MARKER = re.compile(
    r"^\s*PART\s+(I|II|III|IV)\b[\s.:\-–—]*([A-Z][A-Za-z0-9 /,&'\-]{0,80})?\s*$",
    re.MULTILINE,
)
_ATTACHMENT_MARKER = re.compile(
    r"^\s*ATTACHMENT\s+([A-Z0-9\-]{1,6})\b[\s.:\-–—]*([A-Z][A-Za-z0-9 /,&'\-]{0,80})?\s*$",
    re.MULTILINE,
)
_EXHIBIT_MARKER = re.compile(
    r"^\s*EXHIBIT\s+([A-Z0-9\-]{1,6})\b[\s.:\-–—]*([A-Z][A-Za-z0-9 /,&'\-]{0,80})?\s*$",
    re.MULTILINE,
)
# "G.3", "G.3.1" — subsection numbering within an already-known section.
_SUBSECTION_MARKER = re.compile(
    r"^\s*([A-M])\.(\d{1,2}(?:\.\d{1,2})?)\b[\s.:\-–—]*([A-Z][A-Za-z0-9 /,&'\-]{0,80})?\s*$",
    re.MULTILINE,
)

_SF33_MARKER = re.compile(
    r"SOLICITATION[,]?\s+OFFER\s+AND\s+AWARD|STANDARD\s+FORM\s+33|\bSF\s?33\b",
    re.IGNORECASE,
)

_TOC_HEADING = re.compile(r"TABLE\s+OF\s+CONTENTS", re.IGNORECASE)
_DOTTED_LEADER_LINE = re.compile(r"\.{3,}\s*\d{1,4}\s*$", re.MULTILINE)


def _looks_like_toc_page(text: str) -> bool:
    """A page is a TOC page if it announces itself as one, or if most of
    its lines are dot-leader navigation entries."""

    if _TOC_HEADING.search(text):
        return True
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    leader_lines = len(_DOTTED_LEADER_LINE.findall(text))
    return leader_lines / len(lines) >= 0.4


class PageLike(Protocol):
    page_number: int
    final_text: str | None


@dataclass(frozen=True)
class SectionBoundary:
    page_number: int
    offset: int
    section_code: str | None
    section_title: str
    subsection_code: str | None
    confidence: float
    detection_method: str


@dataclass(frozen=True)
class SectionInfo:
    section_code: str | None
    section_title: str
    subsection_code: str | None
    confidence: float
    detection_method: str

    @property
    def display(self) -> str:
        if self.section_code:
            return f"{self.section_code} — {self.section_title}"
        return self.section_title


def _boundaries_for_page(page_number: int, text: str) -> list[SectionBoundary]:
    found: list[SectionBoundary] = []

    for match in _SECTION_MARKER.finditer(text):
        code = match.group(1).upper()
        title = (match.group(2) or "").strip().title() or UCF_SECTIONS.get(
            code, f"Section {code}"
        )
        found.append(
            SectionBoundary(
                page_number=page_number,
                offset=match.start(),
                section_code=code,
                section_title=UCF_SECTIONS.get(code, title),
                subsection_code=None,
                confidence=0.95,
                detection_method="section_marker",
            )
        )

    for match in _KNOWN_TITLE_LINE.finditer(text):
        code = _UCF_TITLE_TO_CODE.get(match.group(1).strip().lower())
        if code is None:
            continue
        found.append(
            SectionBoundary(
                page_number=page_number,
                offset=match.start(),
                section_code=code,
                section_title=UCF_SECTIONS[code],
                subsection_code=None,
                confidence=0.85,
                detection_method="known_title",
            )
        )

    for match in _PART_MARKER.finditer(text):
        roman = match.group(1).upper()
        title = (match.group(2) or "").strip().title() or f"Part {roman}"
        found.append(
            SectionBoundary(
                page_number=page_number,
                offset=match.start(),
                section_code=f"Part {roman}",
                section_title=title,
                subsection_code=None,
                confidence=0.8,
                detection_method="part_marker",
            )
        )

    for match in _ATTACHMENT_MARKER.finditer(text):
        ident = match.group(1).upper()
        title = (match.group(2) or "").strip().title()
        found.append(
            SectionBoundary(
                page_number=page_number,
                offset=match.start(),
                section_code=f"Attachment {ident}",
                section_title=title or f"Attachment {ident}",
                subsection_code=None,
                confidence=0.85,
                detection_method="attachment_marker",
            )
        )

    for match in _EXHIBIT_MARKER.finditer(text):
        ident = match.group(1).upper()
        title = (match.group(2) or "").strip().title()
        found.append(
            SectionBoundary(
                page_number=page_number,
                offset=match.start(),
                section_code=f"Exhibit {ident}",
                section_title=title or f"Exhibit {ident}",
                subsection_code=None,
                confidence=0.85,
                detection_method="exhibit_marker",
            )
        )

    for match in _SUBSECTION_MARKER.finditer(text):
        code = match.group(1).upper()
        sub = match.group(2)
        title = (match.group(3) or "").strip().title() or UCF_SECTIONS.get(
            code, f"Section {code}"
        )
        found.append(
            SectionBoundary(
                page_number=page_number,
                offset=match.start(),
                section_code=code,
                section_title=UCF_SECTIONS.get(code, title),
                subsection_code=f"{code}.{sub}",
                confidence=0.9,
                detection_method="subsection_marker",
            )
        )

    if page_number == 1 or not found:
        if _SF33_MARKER.search(text[:2000]):
            found.append(
                SectionBoundary(
                    page_number=page_number,
                    offset=0,
                    section_code="SF33",
                    section_title="Solicitation, Offer and Award",
                    subsection_code=None,
                    confidence=0.8,
                    detection_method="sf33_cover",
                )
            )

    found.sort(key=lambda boundary: boundary.offset)
    return found


def build_document_outline(pages: Sequence[PageLike]) -> list[SectionBoundary]:
    """Detect structural section boundaries across a document's pages.

    TOC pages are skipped entirely for heading detection — a TOC lists
    every section up front, and its mentions are navigation references,
    not the section's actual start.
    """

    outline: list[SectionBoundary] = []
    for page in sorted(pages, key=lambda p: p.page_number):
        text = page.final_text or ""
        if not text.strip():
            continue
        if _looks_like_toc_page(text):
            continue
        outline.extend(_boundaries_for_page(page.page_number, text))

    outline.sort(key=lambda boundary: (boundary.page_number, boundary.offset))
    return outline


def resolve_section(
    outline: Sequence[SectionBoundary],
    *,
    page_number: int,
    offset: int | None = None,
) -> SectionInfo | None:
    """Nearest preceding boundary for a (page, offset) position.

    A boundary on the same page only counts if it starts at or before
    `offset` (when given); otherwise the section from a prior page
    carries forward, since UCF sections span many pages.
    """

    best: SectionBoundary | None = None
    for boundary in outline:
        if boundary.page_number > page_number:
            break
        if boundary.page_number == page_number and offset is not None:
            if boundary.offset > offset:
                continue
        best = boundary
    if best is None:
        return None
    return SectionInfo(
        section_code=best.section_code,
        section_title=best.section_title,
        subsection_code=best.subsection_code,
        confidence=best.confidence,
        detection_method=best.detection_method,
    )
