import re
from dataclasses import dataclass


@dataclass
class ExtractionIntent:
    mode: str

    requested_concepts: list[str]

    page_start: int | None
    page_end: int | None

    wants_tables: bool
    wants_all: bool
    wants_summary: bool
    wants_question_answer: bool


STOP_WORDS = {
    "extract",
    "find",
    "give",
    "show",
    "tell",
    "me",
    "the",
    "this",
    "that",
    "document",
    "pdf",
    "file",
    "from",
    "and",
    "or",
    "all",
    "please",
}


def detect_page_range(
    instruction: str,
) -> tuple[int | None, int | None]:

    range_match = re.search(
        r"pages?\s+(\d+)\s*(?:-|to|through)\s*(\d+)",
        instruction,
        re.IGNORECASE,
    )

    if range_match:
        return (
            int(range_match.group(1)),
            int(range_match.group(2)),
        )

    single_match = re.search(
        r"page\s+(\d+)",
        instruction,
        re.IGNORECASE,
    )

    if single_match:
        page = int(single_match.group(1))
        return page, page

    return None, None


def extract_concepts(
    instruction: str,
) -> list[str]:

    words = re.findall(
        r"[A-Za-z0-9][A-Za-z0-9+/#_.-]*",
        instruction.lower(),
    )

    return list(
        dict.fromkeys(
            word
            for word in words
            if len(word) > 2
            and word not in STOP_WORDS
        )
    )


def interpret_request(
    instruction: str,
) -> ExtractionIntent:

    lower = instruction.lower()

    page_start, page_end = detect_page_range(
        instruction
    )

    wants_tables = any(
        phrase in lower
        for phrase in (
            "table",
            "tables",
            "line item",
            "line items",
            "clin",
            "clins",
            "rows",
            "columns",
            "price schedule",
        )
    )

    wants_all = any(
        phrase in lower
        for phrase in (
            "everything",
            "all information",
            "all data",
            "all fields",
            "extract all",
        )
    )

    wants_summary = any(
        phrase in lower
        for phrase in (
            "summarize",
            "summary",
            "overview",
        )
    )

    question_words = (
        "what ",
        "who ",
        "when ",
        "where ",
        "why ",
        "how ",
    )

    wants_question_answer = (
        lower.startswith(question_words)
        or "?" in instruction
    )

    if wants_summary:
        mode = "summary"

    elif wants_tables:
        mode = "table"

    elif wants_question_answer:
        mode = "question"

    else:
        mode = "fields"

    return ExtractionIntent(
        mode=mode,
        requested_concepts=extract_concepts(
            instruction
        ),
        page_start=page_start,
        page_end=page_end,
        wants_tables=wants_tables,
        wants_all=wants_all,
        wants_summary=wants_summary,
        wants_question_answer=(
            wants_question_answer
        ),
    )