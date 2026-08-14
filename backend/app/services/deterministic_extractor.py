from app.schemas.universal_extraction import (
    ExtractedValue,
    SourceEvidence,
)
from app.services.form_field_search import (
    search_form_fields,
)
from app.services.generic_entity_extractor import (
    extract_generic_entities,
)
from app.services.generic_label_extractor import (
    extract_labeled_value,
)


def source_evidence(
    *,
    document_name: str,
    page_number: int,
    source_text: str,
) -> SourceEvidence:

    return SourceEvidence(
        page_number=page_number,
        source_text=source_text[:800],
        source_reference=(
            f"{document_name}, "
            f"page {page_number}"
        ),
    )


def extract_from_page(
    *,
    page,
    document_name: str,
    requested_concepts: list[str],
) -> tuple[
    list[ExtractedValue],
    set[str],
]:

    results: list[
        ExtractedValue
    ] = []

    resolved: set[str] = set()

    text = (
        page.final_text
        or ""
    )

    entities = (
        extract_generic_entities(
            text
        )
    )

    for concept in requested_concepts:

        lower = concept.lower()

        # Email
        if (
            "email" in lower
            and entities["email"]
        ):

            for value in entities["email"]:

                results.append(
                    ExtractedValue(
                        label=concept,
                        value=value,
                        value_type="email",
                        confidence=0.98,
                        extraction_method="regex",
                        evidence=source_evidence(
                            document_name=(
                                document_name
                            ),
                            page_number=(
                                page.page_number
                            ),
                            source_text=value,
                        ),
                    )
                )

            resolved.add(
                concept
            )

            continue

        # Phone
        if (
            (
                "phone" in lower
                or "telephone" in lower
            )
            and entities["phone"]
        ):

            for value in entities["phone"]:

                results.append(
                    ExtractedValue(
                        label=concept,
                        value=value,
                        value_type="phone",
                        confidence=0.98,
                        extraction_method="regex",
                        evidence=source_evidence(
                            document_name=(
                                document_name
                            ),
                            page_number=(
                                page.page_number
                            ),
                            source_text=value,
                        ),
                    )
                )

            resolved.add(concept)

            continue

        # Form fields
        if page.form_fields_json:

            matches = search_form_fields(
                form_fields=(
                    page.form_fields_json
                ),
                requested_concept=concept,
            )

            if matches:

                name, value, score = (
                    matches[0]
                )

                results.append(
                    ExtractedValue(
                        label=concept,
                        value=value,
                        value_type="text",
                        confidence=score,
                        extraction_method=(
                            "form_field"
                        ),
                        evidence=source_evidence(
                            document_name=(
                                document_name
                            ),
                            page_number=(
                                page.page_number
                            ),
                            source_text=(
                                f"{name}: "
                                f"{value}"
                            ),
                        ),
                    )
                )

                resolved.add(
                    concept
                )

                continue

        # Generic labels
        label_value = (
            extract_labeled_value(
                text=text,
                requested_label=concept,
            )
        )

        if label_value:

            results.append(
                ExtractedValue(
                    label=concept,
                    value=label_value,
                    value_type="text",
                    confidence=0.80,
                    extraction_method=(
                        "label_value"
                    ),
                    evidence=source_evidence(
                        document_name=(
                            document_name
                        ),
                        page_number=(
                            page.page_number
                        ),
                        source_text=(
                            label_value
                        ),
                    ),
                )
            )

            resolved.add(
                concept
            )

    return (
        results,
        resolved,
    )
