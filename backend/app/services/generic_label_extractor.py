import re
from dataclasses import dataclass


from app.services.label_rejection import reject_as_field_value


@dataclass(frozen=True)
class LayoutBlock:
    """Minimal geometry view over a PageTextBlock row for layout matching."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float


def normalize_label(
    label: str,
) -> str:

    return " ".join(
        label.strip().split()
    )


# A captured value that starts with another field's marker ("6. REQUISITION
# ...", "A. NAME") is not a value at all — it's the next label on the page,
# picked up because the real value cell was blank/unreadable. Reject the
# whole candidate in that case rather than returning the label as if it
# were data.
_LEADING_FIELD_MARKER = re.compile(
    r"^(?:\d{1,2}\.|[A-Z]\.)\s+[A-Z]{2,}"
)

# A value that legitimately starts with real data can still trail off into
# the *next* field's label when OCR/flattened text runs two columns
# together on one line ("FA300224C0008   6. REQUISITION/PURCHASE NUMBER",
# "Sabrina Daniels   B. TELEPHONE"). Cut the value off right before that
# contamination starts.
_EMBEDDED_FIELD_MARKER = re.compile(
    r"\s+(?:\d{1,2}\.|[A-Z]\.)\s+[A-Z]{2,}"
)

# Same idea for a wide column gap with no numbering at all — two spaces or
# more followed by a capitalized/digit run is almost always a new column,
# never a continuation of the same value.
_WIDE_GAP = re.compile(
    r"[ \t]{2,}(?=[A-Z0-9])"
)


def _trim_contamination(value: str) -> str:
    value = _WIDE_GAP.split(value, maxsplit=1)[0]

    match = _EMBEDDED_FIELD_MARKER.search(value)
    if match:
        value = value[: match.start()]

    return value.strip()


def _looks_like_another_label(
    value: str,
    known_labels: frozenset[str] | None,
) -> bool:
    if not value:
        return True

    if reject_as_field_value(value, known_labels=known_labels):
        return True

    if _LEADING_FIELD_MARKER.match(value):
        return True

    if known_labels and normalize_label(value).lower() in known_labels:
        return True

    return False


def extract_labeled_value_from_layout(
    *,
    blocks: list[LayoutBlock],
    requested_label: str,
    known_labels: frozenset[str] | None = None,
) -> str | None:
    """
    Best-effort geometry-based label -> value lookup for OCR'd pages.

    Finds the block whose text matches the requested label, then looks
    for the nearest block to its right (same row) or immediately below it
    (next row, same-ish column) as the value — mirroring how a person
    reads a form field. Only meaningful when real, non-zero geometry is
    present (native-ingest blocks are stored with placeholder zeros and
    are rejected up front).
    """
    if not blocks:
        return None

    if all(
        block.x0 == 0 and block.y0 == 0 and block.x1 == 0 and block.y1 == 0
        for block in blocks
    ):
        return None

    label = normalize_label(requested_label).lower()

    label_block: LayoutBlock | None = None
    for block in blocks:
        normalized = normalize_label(block.text).lower()
        if normalized and (label in normalized or normalized in label):
            label_block = block
            break

    if label_block is None:
        return None

    # The matched block may be a whole text line ("Contract Title: Master
    # Services Agreement"), not a bare label cell — common when block
    # granularity is per-line rather than per-form-field. In that case the
    # value is already inline; parse it from this block's own text instead
    # of raiding a neighboring block, which would just be the *next*
    # unrelated line. Only search neighboring blocks when this one really
    # is just the bare label (the OCR'd-form-cell case).
    block_normalized = normalize_label(label_block.text).lower()
    remainder = block_normalized.replace(label, "", 1).strip(" \t:#.-")
    if remainder:
        return extract_labeled_value(
            text=label_block.text,
            requested_label=requested_label,
            known_labels=known_labels,
        )

    label_height = max(label_block.y1 - label_block.y0, 1.0)
    label_mid_y = (label_block.y0 + label_block.y1) / 2

    same_row: list[LayoutBlock] = []
    below: list[LayoutBlock] = []

    for block in blocks:
        if block is label_block or not block.text.strip():
            continue

        block_mid_y = (block.y0 + block.y1) / 2

        if (
            abs(block_mid_y - label_mid_y) <= label_height
            and block.x0 > label_block.x1
        ):
            same_row.append(block)
        elif (
            block.y0 >= label_block.y1
            and block.y0 - label_block.y1 <= label_height * 3
        ):
            below.append(block)

    same_row.sort(key=lambda block: block.x0)
    below.sort(key=lambda block: (block.y0, block.x0))

    for candidate in same_row + below:
        value = _trim_contamination(candidate.text)
        if value and not _looks_like_another_label(value, known_labels):
            return value

    return None


def extract_labeled_value(
    *,
    text: str,
    requested_label: str,
    known_labels: frozenset[str] | None = None,
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

                value = _trim_contamination(
                    match.group(1)
                )

                if value and not _looks_like_another_label(value, known_labels):
                    return value

    return None
