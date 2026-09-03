from difflib import SequenceMatcher

from app.services.generic_kv_scanner import is_internal_form_name


def normalize_name(
    value: str,
) -> str:

    return "".join(
        character.lower()
        for character in value
        if character.isalnum()
    )


def similarity(
    first: str,
    second: str,
) -> float:

    return SequenceMatcher(
        None,
        normalize_name(first),
        normalize_name(second),
    ).ratio()


def search_form_fields(
    *,
    form_fields: dict[str, str],
    requested_concept: str,
    minimum_score: float = 0.45,
) -> list[
    tuple[str, str, float]
]:

    matches = []

    for name, value in form_fields.items():
        if is_internal_form_name(name):
            continue

        score = similarity(
            name,
            requested_concept,
        )

        searchable = (
            f"{name} {value}"
        ).lower()

        if (
            requested_concept.lower()
            in searchable
        ):
            score += 0.4

        if score >= minimum_score:

            matches.append(
                (
                    name,
                    value,
                    min(score, 1.0),
                )
            )

    matches.sort(
        key=lambda item:
            -item[2]
    )

    return matches
