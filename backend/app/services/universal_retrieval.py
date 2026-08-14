from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_page import DocumentPage
from app.services.request_interpreter import (
    ExtractionIntent,
)


def score_text(
    text: str,
    concepts: list[str],
) -> float:

    lower = text.lower()

    score = 0.0

    for concept in concepts:

        count = lower.count(
            concept.lower()
        )

        score += count

    return score


def score_form_fields(
    form_fields: dict | None,
    concepts: list[str],
) -> float:

    if not form_fields:
        return 0.0

    searchable = " ".join(
        f"{key} {value}"
        for key, value
        in form_fields.items()
    ).lower()

    score = 0.0

    for concept in concepts:

        score += (
            searchable.count(
                concept.lower()
            )
            * 3.0
        )

    return score


def score_tables(
    tables: list | None,
    concepts: list[str],
) -> float:

    if not tables:
        return 0.0

    searchable = str(
        tables
    ).lower()

    score = 0.0

    for concept in concepts:

        score += (
            searchable.count(
                concept.lower()
            )
            * 2.0
        )

    return score


def retrieve_pages(
    *,
    database: Session,
    document_id: str,
    intent: ExtractionIntent,
    maximum_pages: int,
) -> list[DocumentPage]:

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

    # Explicit page range wins.
    if intent.page_start is not None:

        ending = (
            intent.page_end
            or intent.page_start
        )

        return [
            page
            for page in pages
            if (
                intent.page_start
                <= page.page_number
                <= ending
            )
        ]

    if not intent.requested_concepts:

        return pages[
            :maximum_pages
        ]

    ranked: list[
        tuple[float, DocumentPage]
    ] = []

    for page in pages:

        score = 0.0

        score += score_text(
            page.final_text or "",
            intent.requested_concepts,
        )

        score += score_form_fields(
            page.form_fields_json,
            intent.requested_concepts,
        )

        score += score_tables(
            page.tables_json,
            intent.requested_concepts,
        )

        if (
            intent.wants_tables
            and page.has_tables
        ):
            score += 1.5

        if score > 0:
            ranked.append(
                (
                    score,
                    page,
                )
            )

    ranked.sort(
        key=lambda item: (
            -item[0],
            item[1].page_number,
        )
    )

    return [
        page
        for _, page
        in ranked[:maximum_pages]
    ]