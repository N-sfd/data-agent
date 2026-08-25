import re
from dataclasses import dataclass

from app.models.document_page import DocumentPage
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


@dataclass(frozen=True)
class ClauseCitation:
    clause_family: str
    clause_number: str
    title: str
    page_number: int
    source_text: str


def _scan_page_for_family(
    *,
    page: DocumentPage,
    pattern: re.Pattern[str],
    family: str,
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

        seen.add(clause_number)
        citations.append(
            ClauseCitation(
                clause_family=family,
                clause_number=clause_number,
                title=title,
                page_number=page.page_number,
                source_text=source_text[:240],
            )
        )

    return citations


def scan_pages_for_clause_citations(
    *,
    pages: list[DocumentPage],
    family_filter: str | None = None,
) -> list[ClauseCitation]:
    """Extract FAR/DFARS clause numbers from page text before AI fallback."""
    citations: list[ClauseCitation] = []

    for page in pages:
        if family_filter in {None, "FAR", "far_clauses"}:
            citations.extend(
                _scan_page_for_family(
                    page=page,
                    pattern=FAR_CLAUSE_PATTERN,
                    family="FAR",
                )
            )
        if family_filter in {None, "DFARS", "dfars_clauses"}:
            citations.extend(
                _scan_page_for_family(
                    page=page,
                    pattern=DFARS_CLAUSE_PATTERN,
                    family="DFARS",
                )
            )

    return citations
