import re
from dataclasses import dataclass

from app.models.document_page import DocumentPage
from app.schemas.candidate_classification import StructuralRegion
from app.services.source_validator import validate_source_value

# Title capture deliberately uses [ \t]+ (not \s+): \s+ matches newlines
# too, which let a clause number immediately followed by a DIFFERENT
# clause number on the next line get that next number captured as if it
# were the first clause's title (confirmed by a line-level regression
# test). The title, when captured at all, must be on the same source line.
FAR_CLAUSE_PATTERN = re.compile(
    r"\b(52\.\d{3}-\d+(?:\s+Alt(?:ernate)?\s+[IVXLC\d]+)?)"
    r"(?:[ \t]+([^\n]{5,120}))?",
    re.IGNORECASE,
)

DFARS_CLAUSE_PATTERN = re.compile(
    r"\b(252\.\d{3}-\d+)"
    r"(?:[ \t]+([^\n]{5,120}))?",
    re.IGNORECASE,
)

# GSAR (General Services Administration Acquisition Regulation), e.g.
# "552.216-75 Transactional Data Reporting" - confirmed present in the
# regression contract's Section I incorporated-clauses listing (decision
# #2 in docs/v3-implementation-plan.md: routes into Clauses with
# Regulation="GSAR", handled at the routing layer, not here).
GSAR_CLAUSE_PATTERN = re.compile(
    r"\b(552\.\d{3}-\d+)"
    r"(?:[ \t]+([^\n]{5,120}))?",
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
    # Positive-evidence basis for `listing_context` (P0 quality-gate
    # follow-up): "EXPLICIT_LISTING" (table-style Clause/Title-and-Date
    # entry), "LISTING_CONTEXT" (numbered full-text incorporation heading,
    # e.g. "I.2.4.2 FAR 52.204-30 ..."), "CLAUSE_BODY_REFERENCE" (inside the
    # incorporated-clauses section but not itself an entry/heading - a
    # cross-reference within a clause's own body text), "NARRATIVE_REFERENCE"
    # (outside the incorporated-clauses section entirely), "TOC", or
    # "AMBIGUOUS". Page density alone is never sufficient evidence - see
    # docs/v3-implementation-plan.md quality-gate notes.
    classification_basis: str = "AMBIGUOUS"
    alternate: str | None = None
    deviation: str | None = None


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


# Positive structural evidence for the incorporated-clauses section
# (UCF Section I), used to bound where a citation is even ELIGIBLE to be
# classified as an incorporated Clause. A citation matching a clause-shaped
# regex outside these bounds is always a reference, never a listing entry -
# page density inside these bounds is likewise never sufficient on its own
# (see quality-gate follow-up): each occurrence still needs its own entry/
# heading shape (below) to become EXPLICIT_LISTING/LISTING_CONTEXT.
# Excludes Table-of-Contents entries for these same section headings
# ("SECTION I - CONTRACT CLAUSES.......................74") via a negative
# lookahead for the dot-leader/page-number tail on the same line - without
# it, the TOC page (which lists every section heading back to back) is
# mistaken for the real heading, collapsing the bounds to near zero-width.
_TOC_TAIL_NEGATIVE_LOOKAHEAD = r"(?!.*\.{2,}\s*\d+\s*$)"
_SECTION_I_START_RE = re.compile(
    rf"^\s*SECTION\s+I\b{_TOC_TAIL_NEGATIVE_LOOKAHEAD}", re.IGNORECASE | re.MULTILINE
)
_SECTION_BOUNDARY_RE = re.compile(
    rf"^\s*SECTION\s+[A-HJ-Z]\b{_TOC_TAIL_NEGATIVE_LOOKAHEAD}",
    re.IGNORECASE | re.MULTILINE,
)

# "I.2.4.2 FAR 52.204-30 Federal Acquisition Supply Chain Security Act
# Orders-Prohibition." - a numbered subsection heading whose own text IS the
# incorporation-by-full-text entry for that clause (LISTING_CONTEXT).
_FULLTEXT_CLAUSE_HEADING_RE = re.compile(
    r"^\s*I\.\d+(?:\.\d+)+\s+(?:FAR|DFARS|GSAR|GSAM/R)\s+\d{2,3}\.\d{3}-\d+",
    re.IGNORECASE | re.MULTILINE,
)

# A reconstructed title ending in a date parenthetical, optionally followed
# by an Alternate/Deviation tail - "Definitions. (JUN 2020)",
# "... (FEB 2018) (DEVIATION FAR 53.232-39)", "... (JUN 2020) - Alternate I
# (NOV 2021)". This is the actual shape of a real Clause/Title-and-Date
# table entry (EXPLICIT_LISTING) - a bare mention of a clause number in
# running prose never ends this way.
_LISTING_TITLE_DATE_RE = re.compile(
    r"\(\s*[A-Za-z]{3,9}\.?\s+\d{4}\s*\)\s*(?:-?\s*Alternate\s+[IVXLC\d]+\s*(?:\([^)]*\))?)?"
    r"\s*(?:\(DEVIATION[^)]*\))?\s*$",
    re.IGNORECASE,
)

_ALTERNATE_RE = re.compile(r"Alternate\s+([IVXLC\d]+)", re.IGNORECASE)
_DEVIATION_RE = re.compile(r"\(DEVIATION[^)]*\)", re.IGNORECASE)


def _find_section_i_bounds(pages: list[DocumentPage]) -> tuple[int, int] | None:
    """Returns (start_page_number, end_page_number_exclusive) for the
    incorporated-clauses section, or None if no "SECTION I" heading is
    found (callers must not assume the whole document is in-bounds then)."""

    ordered = sorted(pages, key=lambda p: p.page_number)
    start_page: int | None = None
    for page in ordered:
        if _SECTION_I_START_RE.search(page.final_text or ""):
            start_page = page.page_number
            break
    if start_page is None:
        return None

    end_page = ordered[-1].page_number + 1
    for page in ordered:
        if page.page_number <= start_page:
            continue
        text = page.final_text or ""
        if _SECTION_BOUNDARY_RE.search(text) and not _SECTION_I_START_RE.search(text):
            end_page = page.page_number
            break
    return start_page, end_page


def _looks_like_listing_entry(*, source_text: str, title: str) -> bool:
    return bool(_LISTING_TITLE_DATE_RE.search(title or "")) or bool(
        _LISTING_TITLE_DATE_RE.search(source_text or "")
    )


def _looks_like_fulltext_heading(source_text: str) -> bool:
    return bool(_FULLTEXT_CLAUSE_HEADING_RE.search(source_text or ""))


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


def _reconstruct_title_from_neighboring_region(
    *,
    clause_number: str,
    page_regions: list[StructuralRegion] | None,
) -> str | None:
    """When the same-line regex capture yields no usable title (e.g. the
    clause number sits on its own line: "52.204-21" with the title on the
    next line), look at the next structural region on this page for a
    short, non-citation line to use as the title - line-level neighbor
    lookup, not a rewrite of the citation scanner itself."""

    if not page_regions:
        return None

    ordered = sorted(page_regions, key=lambda r: r.block_index)
    for index, region in enumerate(ordered):
        if clause_number not in region.text:
            continue
        for candidate in ordered[index + 1 : index + 2]:
            if FAR_CLAUSE_PATTERN.search(candidate.text) or DFARS_CLAUSE_PATTERN.search(
                candidate.text
            ) or GSAR_CLAUSE_PATTERN.search(candidate.text):
                # The very next region is itself another citation - not a
                # title continuation.
                return None
            words = candidate.text.split()
            if 1 <= len(words) <= 12:
                return candidate.text.strip().rstrip(".")
        return None
    return None


def _classify_citation(
    *,
    page_number: int,
    source_text: str,
    title: str,
    section_i_bounds: tuple[int, int] | None,
    region_listing_context: bool | None,
) -> tuple[bool, str]:
    """Returns (listing_context, classification_basis). Positive-evidence
    only: page density is never sufficient (quality-gate follow-up) - each
    occurrence needs its own entry/heading shape, and must fall inside the
    incorporated-clauses section (Section I) to be listing-eligible at all.
    """

    if section_i_bounds is None:
        # No literal "SECTION I"-style heading found anywhere in this
        # document - section-bounded evidence doesn't apply to this format.
        # Fall back to the structure-classifier's own region signal rather
        # than assuming narrative (preserves pre-quality-gate behavior for
        # non-UCF-lettered contracts) - still never defaults an unknown
        # signal to True.
        if region_listing_context is True:
            return True, "LISTING_CONTEXT"
        if region_listing_context is False:
            return False, "NARRATIVE_REFERENCE"
        return False, "AMBIGUOUS"

    in_section_i = section_i_bounds[0] <= page_number < section_i_bounds[1]

    if not in_section_i:
        return False, "NARRATIVE_REFERENCE"

    if _looks_like_fulltext_heading(source_text):
        return True, "LISTING_CONTEXT"

    if _looks_like_listing_entry(source_text=source_text, title=title):
        return True, "EXPLICIT_LISTING"

    # Inside Section I, but this specific occurrence has neither a
    # recognizable table entry shape nor a full-text heading shape - most
    # likely a cross-reference inside a clause's own body text (e.g. "(see
    # FAR clause 52.232-17, Interest)" inside a different clause's
    # boilerplate). Never promoted to Clause; still visible as a reference.
    if region_listing_context is False:
        return False, "CLAUSE_BODY_REFERENCE"
    return False, "AMBIGUOUS"


def _scan_page_for_family(
    *,
    page: DocumentPage,
    pattern: re.Pattern[str],
    family: str,
    page_regions: list[StructuralRegion] | None = None,
    section_i_bounds: tuple[int, int] | None = None,
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

        if not title:
            reconstructed = _reconstruct_title_from_neighboring_region(
                clause_number=clause_number,
                page_regions=page_regions,
            )
            if reconstructed:
                title = reconstructed
                source_text = f"{source_text} {reconstructed}".strip()

        if not validate_source_value(
            value=clause_number,
            source_text=source_text,
            page_text=text,
        ):
            continue

        try:
            region_listing_context = _region_says_listing_context(
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

        listing_context, classification_basis = _classify_citation(
            page_number=page.page_number,
            source_text=source_text,
            title=title,
            section_i_bounds=section_i_bounds,
            region_listing_context=region_listing_context,
        )

        alternate_match = _ALTERNATE_RE.search(title) or _ALTERNATE_RE.search(clause_number)
        deviation_match = _DEVIATION_RE.search(title) or _DEVIATION_RE.search(source_text)

        seen.add(clause_number)
        citations.append(
            ClauseCitation(
                clause_family=family,
                clause_number=clause_number,
                title=title,
                page_number=page.page_number,
                source_text=source_text[:240],
                listing_context=listing_context,
                classification_basis=classification_basis,
                alternate=alternate_match.group(1) if alternate_match else None,
                deviation=deviation_match.group(0) if deviation_match else None,
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
    section_i_bounds = _find_section_i_bounds(pages)

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
                    section_i_bounds=section_i_bounds,
                )
            )
        if family_filter in {None, "DFARS", "dfars_clauses"}:
            citations.extend(
                _scan_page_for_family(
                    page=page,
                    pattern=DFARS_CLAUSE_PATTERN,
                    family="DFARS",
                    page_regions=page_regions,
                    section_i_bounds=section_i_bounds,
                )
            )
        if family_filter in {None, "GSAR", "gsar_clauses"}:
            citations.extend(
                _scan_page_for_family(
                    page=page,
                    pattern=GSAR_CLAUSE_PATTERN,
                    family="GSAR",
                    page_regions=page_regions,
                    section_i_bounds=section_i_bounds,
                )
            )

    return citations
