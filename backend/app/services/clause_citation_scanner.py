import re
from dataclasses import dataclass

from app.models.document_page import DocumentPage
from app.schemas.candidate_classification import StructuralRegion
from app.services.source_validator import validate_source_value

FAR_CLAUSE_PATTERN = re.compile(
    r"\b(52\.\d{3}-\d+(?:\s+Alt(?:ernate)?\s+[IVXLC\d]+)?)"
    r"(?:\s+([^\n]{5,120}))?",
    re.IGNORECASE,
)

DFARS_CLAUSE_PATTERN = re.compile(
    r"\b(252\.\d{3}-\d+)"
    r"(?:\s+([^\n]{5,120}))?",
    re.IGNORECASE,
)

# GSAR (General Services Administration Acquisition Regulation), e.g.
# "552.216-75 Transactional Data Reporting" - confirmed present in the
# regression contract's Section I incorporated-clauses listing (decision
# #2 in docs/v3-implementation-plan.md: routes into Clauses with
# Regulation="GSAR", handled at the routing layer, not here).
GSAR_CLAUSE_PATTERN = re.compile(
    r"\b(552\.\d{3}-\d+)"
    r"(?:\s+([^\n]{5,120}))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClauseCitation:
    clause_family: str
    clause_number: str
    title: str
    page_number: int
    source_text: str
    # True when this citation's source block was classified CLAUSE_LISTING
    # by the Step 1 structure classifier (a short, isolated citation line -
    # e.g. an incorporated-clauses list), False when it appeared inside a
    # NARRATIVE block (an incidental in-prose mention), None when no
    # structural region information was supplied (caller didn't pass
    # `regions`) - callers must not assume False/incidental in that case.
    listing_context: bool | None = None


# Region types whose text is document scaffolding (a Table of Contents
# entry listing a clause's title/page number, a heading, page furniture) -
# a clause number appearing inside one of these is NOT a real citation of
# that clause at all (it's the document's own navigation aid), so it must
# be excluded entirely rather than falling through to FAR_REFERENCE. This
# is the clause-citation analog of the TOC protection already applied to
# ordinary field candidates in structure_classifier.py/candidate_router.py.
_STRUCTURAL_NOISE_REGION_TYPES = frozenset(
    {"TOC_ENTRY", "SECTION_HEADING", "SUBSECTION_HEADING", "FOOTER_HEADER"}
)


class _ToCNoise(Exception):
    """Internal signal: this clause-number match is inside TOC/heading/
    footer scaffolding, not a real citation - drop it, don't classify it."""


def _region_says_listing_context(
    *,
    clause_number: str,
    page_regions: list[StructuralRegion] | None,
) -> bool | None:
    """True = listing context, False = narrative context, None = unknown
    (no regions supplied). Raises `_ToCNoise` when the citation's own block
    is TOC/heading/footer scaffolding - callers must drop the citation."""

    if page_regions is None:
        return None
    for region in page_regions:
        if clause_number not in region.text:
            continue
        if region.region_type in _STRUCTURAL_NOISE_REGION_TYPES:
            raise _ToCNoise
        if region.region_type == "CLAUSE_LISTING":
            return True
        if region.region_type == "NARRATIVE":
            return False
    # The citation's block wasn't classified either way (e.g. it landed in
    # TABLE_ROW, which is itself listing-shaped) - treat table rows as
    # listing context too; anything else is genuinely unknown.
    for region in page_regions:
        if clause_number in region.text and region.region_type == "TABLE_ROW":
            return True
    return None


def _scan_page_for_family(
    *,
    page: DocumentPage,
    pattern: re.Pattern[str],
    family: str,
    page_regions: list[StructuralRegion] | None = None,
) -> list[ClauseCitation]:
    text = page.final_text or ""
    if not text.strip():
        return []

    citations: list[ClauseCitation] = []
    seen: set[str] = set()

    for match in pattern.finditer(text):
        clause_number = match.group(1).strip()
        title = (match.group(2) or "").strip().rstrip(".")
        source_text = match.group(0).strip()

        if clause_number in seen:
            continue

        if not validate_source_value(
            value=clause_number,
            source_text=source_text,
            page_text=text,
        ):
            continue

        try:
            listing_context = _region_says_listing_context(
                clause_number=clause_number,
                page_regions=page_regions,
            )
        except _ToCNoise:
            # A Table-of-Contents/heading line referencing this clause's
            # title (e.g. "I.2.1 FAR 52.216-32 Task-Order and Delivery-
            # Order Ombudsman ... 74") is not a citation of the clause -
            # it's the document's own navigation. Drop it silently; it
            # will still be found as a real citation wherever it actually
            # appears in the clause listing or narrative body.
            continue

        seen.add(clause_number)
        citations.append(
            ClauseCitation(
                clause_family=family,
                clause_number=clause_number,
                title=title,
                page_number=page.page_number,
                source_text=source_text[:240],
                listing_context=listing_context,
            )
        )

    return citations


def scan_pages_for_clause_citations(
    *,
    pages: list[DocumentPage],
    family_filter: str | None = None,
    regions_by_page: dict[int, list[StructuralRegion]] | None = None,
) -> list[ClauseCitation]:
    """Extract FAR/DFARS/GSAR clause numbers from page text before AI
    fallback.

    `regions_by_page`, when supplied (Step 1 structure classifier output,
    keyed by page_number), lets each citation report whether it came from a
    clause-listing context (an incorporated-clauses list) or a narrative
    in-prose mention - callers use this to route CLAUSE vs FAR_REFERENCE.
    Omitting it preserves the original text-only behavior with
    `listing_context=None` on every result.
    """
    citations: list[ClauseCitation] = []

    for page in pages:
        page_regions = (
            regions_by_page.get(page.page_number) if regions_by_page else None
        )
        if family_filter in {None, "FAR", "far_clauses"}:
            citations.extend(
                _scan_page_for_family(
                    page=page,
                    pattern=FAR_CLAUSE_PATTERN,
                    family="FAR",
                    page_regions=page_regions,
                )
            )
        if family_filter in {None, "DFARS", "dfars_clauses"}:
            citations.extend(
                _scan_page_for_family(
                    page=page,
                    pattern=DFARS_CLAUSE_PATTERN,
                    family="DFARS",
                    page_regions=page_regions,
                )
            )
        if family_filter in {None, "GSAR", "gsar_clauses"}:
            citations.extend(
                _scan_page_for_family(
                    page=page,
                    pattern=GSAR_CLAUSE_PATTERN,
                    family="GSAR",
                    page_regions=page_regions,
                )
            )

    return citations
