import re


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9.-]+\."
    r"[A-Za-z]{2,}\b"
)


PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+?1[\s.-]?)?"
    r"(?:\(?\d{3}\)?[\s.-]?)"
    r"\d{3}[\s.-]?\d{4}"
    r"(?!\d)"
)


MONEY_PATTERN = re.compile(
    r"\bUSD\s+[\d,]+(?:\.\d{2})?"
    r"|"
    r"\$[\d,]+(?:\.\d{2})?"
)


DATE_PATTERN = re.compile(
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    r"|"
    r"\b\d{1,2}\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[A-Za-z]*\s+\d{4}\b",
    re.IGNORECASE,
)


def extract_generic_entities(
    text: str,
) -> dict[str, list[str]]:

    return {
        "email": list(
            dict.fromkeys(
                EMAIL_PATTERN.findall(
                    text
                )
            )
        ),

        "phone": list(
            dict.fromkeys(
                PHONE_PATTERN.findall(
                    text
                )
            )
        ),

        "money": list(
            dict.fromkeys(
                MONEY_PATTERN.findall(
                    text
                )
            )
        ),

        "date": list(
            dict.fromkeys(
                DATE_PATTERN.findall(
                    text
                )
            )
        ),
    }
