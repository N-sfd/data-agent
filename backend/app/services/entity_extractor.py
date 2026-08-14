import re


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


PHONE_PATTERN = re.compile(
    r"(?:\+?1[\s.-]?)?"
    r"(?:\(?\d{3}\)?[\s.-]?)"
    r"\d{3}[\s.-]?\d{4}"
)


MONEY_PATTERN = re.compile(
    r"(?:USD\s*)?"
    r"\$"
    r"\s?"
    r"\d[\d,]*"
    r"(?:\.\d{2})?"
)


DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}/\d{1,2}/\d{2,4}"
    r"|"
    r"\d{1,2}\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\s+\d{4}"
    r")\b",
    re.IGNORECASE,
)


def find_generic_entities(
    text: str,
) -> dict:

    return {
        "emails":
            list(dict.fromkeys(
                EMAIL_PATTERN.findall(text)
            )),

        "phones":
            list(dict.fromkeys(
                PHONE_PATTERN.findall(text)
            )),

        "money":
            list(dict.fromkeys(
                MONEY_PATTERN.findall(text)
            )),

        "dates":
            list(dict.fromkeys(
                DATE_PATTERN.findall(text)
            )),
    }
