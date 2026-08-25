import re
import unicodedata

_PUNCTUATION_VARIANTS = {
    "‐": "-",  # hyphen
    "‑": "-",  # non-breaking hyphen
    "‒": "-",  # figure dash
    "–": "-",  # en dash
    "—": "-",  # em dash
    "‘": "'",  # left single quote
    "’": "'",  # right single quote
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    " ": " ",  # non-breaking space
}


def normalize_text(
    value: str,
) -> str:

    value = unicodedata.normalize(
        "NFKC",
        value,
    )

    for variant, replacement in (
        _PUNCTUATION_VARIANTS.items()
    ):
        value = value.replace(
            variant,
            replacement,
        )

    value = value.lower()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def validate_source_value(
    *,
    value: object,
    source_text: str,
    page_text: str,
) -> bool:

    if value is None:
        return False

    if isinstance(
        value,
        (
            list,
            dict,
        ),
    ):
        return bool(
            source_text.strip()
        )

    normalized_value = normalize_text(
        str(value)
    )

    normalized_source = normalize_text(
        source_text
    )

    normalized_page = normalize_text(
        page_text
    )

    if (
        normalized_value
        in normalized_page
    ):
        return True

    if (
        normalized_source
        and normalized_source
        in normalized_page
    ):
        return True

    return False
