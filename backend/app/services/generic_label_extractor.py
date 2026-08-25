import re


def normalize_label(
    label: str,
) -> str:

    return " ".join(
        label.strip().split()
    )


def extract_labeled_value(
    *,
    text: str,
    requested_label: str,
) -> str | None:

    label = normalize_label(
        requested_label
    )

    # A plural request token ("dates") should still match a singular
    # label in the document ("Date:"), and vice versa isn't needed since
    # the singular form is already a substring match candidate below.
    candidates = [label]

    if label.endswith("s") and len(label) > 3:
        candidates.append(label[:-1])

    for candidate in candidates:

        escaped = re.escape(candidate)

        patterns = [
            rf"{escaped}\s*[:#.-]\s*([^\n]+)",
            rf"{escaped}\s+([^\n]{{1,160}})",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:

                value = (
                    match.group(1)
                    .strip()
                )

                if value:
                    return value

    return None
