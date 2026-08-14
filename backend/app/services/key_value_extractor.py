import re


def find_label_value(
    text: str,
    label: str,
) -> str | None:

    escaped = re.escape(
        label
    )

    patterns = [
        rf"{escaped}\s*[:#-]\s*([^\n]+)",
        rf"{escaped}\s+([A-Z0-9][^\n]{{0,100}})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:

            value = (
                match
                .group(1)
                .strip()
            )

            return value

    return None
