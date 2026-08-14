from app.schemas.universal_extraction import (
    ExtractedTable,
)


def table_matches_request(
    table: dict,
    concepts: list[str],
) -> bool:

    if not concepts:
        return True

    searchable = str(
        table
    ).lower()

    def matches(concept: str) -> bool:
        lowered = concept.lower()

        if lowered in searchable:
            return True

        # A plural request token ("clins") should still match a singular
        # table header/value ("CLIN").
        if lowered.endswith("s") and len(lowered) > 3:
            return lowered[:-1] in searchable

        return False

    return any(
        matches(concept)
        for concept in concepts
    )


def extract_requested_tables(
    *,
    pages,
    document_name: str,
    concepts: list[str],
) -> list[ExtractedTable]:

    results: list[
        ExtractedTable
    ] = []

    for page in pages:

        for table in (
            page.tables_json or []
        ):

            if not table_matches_request(
                table,
                concepts,
            ):
                continue

            results.append(
                ExtractedTable(
                    table_id=(
                        table.get(
                            "table_id",
                            (
                                f"{page.page_number}"
                                "-table"
                            ),
                        )
                    ),

                    title=table.get(
                        "title"
                    ),

                    headers=table.get(
                        "headers",
                        [],
                    ),

                    rows=table.get(
                        "rows",
                        [],
                    ),

                    page_number=(
                        page.page_number
                    ),

                    confidence=0.85,

                    source_reference=(
                        f"{document_name}, "
                        f"page "
                        f"{page.page_number}"
                    ),
                )
            )

    return results
