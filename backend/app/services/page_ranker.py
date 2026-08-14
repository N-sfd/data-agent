import json
import re

from app.models.document_page import DocumentPage


def _parse_json_field(raw: object) -> object:
    if raw is None:
        return None

    if isinstance(raw, (dict, list)):
        return raw

    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    return None


def score_page(
    *,
    page: DocumentPage,
    keywords: list[str],
    instruction: str | None = None,
) -> float:

    text = (
        page.final_text
        or ""
    ).lower()

    score = 0.0

    if instruction:
        phrase = instruction.lower().strip()

        if len(phrase) >= 8 and phrase in text:
            score += 5.0

        # Multi-word phrase fragments improve conceptual hits.
        tokens = [
            token
            for token in re.findall(r"[a-z0-9][a-z0-9_-]+", phrase)
            if len(token) > 3
        ]

        for index in range(len(tokens) - 1):
            bigram = f"{tokens[index]} {tokens[index + 1]}"

            if bigram in text:
                score += 2.0

    for keyword in keywords:

        score += (
            text.count(keyword)
            * 1.0
        )

    form_fields = _parse_json_field(page.form_fields_json)

    if isinstance(form_fields, dict) and form_fields:

        form_text = " ".join(
            [
                str(key)
                + " "
                + str(value)
                for key, value
                in form_fields.items()
            ]
        ).lower()

        for keyword in keywords:
            score += (
                form_text.count(
                    keyword
                )
                * 3.0
            )

        if instruction:
            phrase = instruction.lower().strip()

            if phrase and phrase in form_text:
                score += 6.0

    tables = _parse_json_field(page.tables_json)

    if tables:

        table_text = str(
            tables
        ).lower()

        for keyword in keywords:
            score += (
                table_text.count(
                    keyword
                )
                * 2.0
            )

        if isinstance(tables, list):
            header_text = " ".join(
                " ".join(table.get("headers", []))
                for table in tables
                if isinstance(table, dict)
            ).lower()

            for keyword in keywords:
                score += header_text.count(keyword) * 2.5

    return score
