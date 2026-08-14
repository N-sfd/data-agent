import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_page import DocumentPage
from app.services.page_ranker import score_page


STOP_WORDS = {
    "the",
    "this",
    "that",
    "from",
    "only",
    "please",
    "extract",
    "show",
    "find",
    "convert",
    "table",
    "tables",
    "financial",
    "report",
}


def detect_page_range(
    instruction: str,
) -> tuple[int | None, int | None]:

    patterns = [
        r"pages?\s+(\d+)\s*(?:-|to|through)\s*(\d+)",
        r"page\s+(\d+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            instruction,
            re.IGNORECASE,
        )

        if not match:
            continue

        if len(match.groups()) == 2:
            return (
                int(match.group(1)),
                int(match.group(2)),
            )

        page = int(match.group(1))

        return page, page

    return None, None


def get_search_terms(
    instruction: str,
) -> list[str]:

    words = re.findall(
        r"[A-Za-z][A-Za-z0-9_-]+",
        instruction.lower(),
    )

    return [
        word
        for word in words
        if len(word) > 2
        and word not in STOP_WORDS
    ]


def select_relevant_pages(
    *,
    database: Session,
    document_id: str,
    instruction: str,
    page_start: int | None = None,
    page_end: int | None = None,
    maximum_pages: int = 10,
) -> list[int]:

    detected_start, detected_end = (
        detect_page_range(instruction)
    )

    first_page = (
        page_start
        if page_start is not None
        else detected_start
    )

    last_page = (
        page_end
        if page_end is not None
        else detected_end
    )

    pages = list(
        database.scalars(
            select(DocumentPage)
            .where(
                DocumentPage.document_id
                == document_id
            )
            .order_by(
                DocumentPage.page_number
            )
        )
    )

    if first_page is not None:

        ending_page = (
            last_page
            if last_page is not None
            else first_page
        )

        return [
            page.page_number
            for page in pages
            if first_page
            <= page.page_number
            <= ending_page
        ]

    terms = get_search_terms(
        instruction
    )

    if not terms:
        return []

    scored_pages: list[
        tuple[float, int]
    ] = []

    for page in pages:

        score = score_page(
            page=page,
            keywords=terms,
            instruction=instruction,
        )

        if score > 0:
            scored_pages.append(
                (
                    score,
                    page.page_number,
                )
            )

    scored_pages.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected = [
        page_number
        for _, page_number
        in scored_pages[:maximum_pages]
    ]

    return sorted(selected)
