from __future__ import annotations

import json
import re
from uuid import uuid4

from app.models.document_page import DocumentPage
from app.schemas.universal_extraction import (
    ExtractedTable,
    ExtractedValue,
    SourceEvidence,
    UniversalExtractionResponse,
)
from app.services.generic_entity_extractor import (
    extract_generic_entities,
)
from app.services.key_value_extractor import find_label_value
from app.services.request_interpreter import ExtractionIntent


def _as_structured(raw: object) -> object:
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


def _parse_json(raw: object) -> object:
    return _as_structured(raw)


def _source_reference(
    page: DocumentPage,
) -> str:
    return f"document page {page.page_number}"


def _normalize_concept(text: str) -> str:
    normalized = text.strip().lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", normalized)


def _concept_matches(concept: str, *texts: str) -> bool:
    needle = _normalize_concept(concept)

    if not needle:
        return False

    # Cheap singular/plural handling ("dates" should still match "date").
    singular = needle[:-1] if needle.endswith("s") and len(needle) > 3 else needle

    for text in texts:
        haystack = _normalize_concept(text)

        if needle in haystack or singular in haystack:
            return True

    return False


def _snippet(text: str, needle: str, radius: int = 120) -> str:
    lower = text.lower()
    index = lower.find(needle.lower())

    if index < 0:
        return text[: radius * 2].strip()

    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)

    return text[start:end].strip()


def _table_matches_request(
    table: dict,
    instruction: str,
    concepts: list[str],
) -> bool:
    blob = (
        " ".join(str(header) for header in table.get("headers", []))
        + " "
        + str(table.get("rows", []))
    )

    if concepts:
        # Concepts were requested: only keep tables that actually relate to
        # them, instead of matching any table just because the instruction
        # happens to mention the word "table".
        return any(_concept_matches(concept, blob) for concept in concepts)

    # No specific concepts requested - keep tables when the user asked for
    # tables broadly.
    lower_instruction = instruction.lower()
    return "table" in lower_instruction or "clin" in lower_instruction


def extract_requested_tables(
    *,
    pages: list[DocumentPage],
    instruction: str,
    concepts: list[str],
) -> tuple[list[ExtractedTable], list[str]]:
    tables: list[ExtractedTable] = []
    warnings: list[str] = []

    for page in pages:
        stored = _parse_json(page.tables_json)

        if not isinstance(stored, list):
            continue

        for table in stored:
            if not isinstance(table, dict):
                continue

            headers = table.get("headers") or []
            rows = table.get("rows") or []

            if not headers or not rows:
                continue

            if concepts and not _table_matches_request(
                table,
                instruction,
                concepts,
            ):
                continue

            tables.append(
                ExtractedTable(
                    table_id=str(uuid4()),
                    title=None,
                    headers=list(headers),
                    rows=list(rows),
                    page_number=page.page_number,
                    confidence=0.82,
                    source_reference=_source_reference(page),
                )
            )

    if not tables:
        warnings.append(
            "No matching tables were found on the selected pages."
        )

    return tables, warnings


def answer_from_pages(
    *,
    pages: list[DocumentPage],
    instruction: str,
    concepts: list[str],
) -> tuple[str | None, list[ExtractedValue], list[str], list[str]]:
    values: list[ExtractedValue] = []
    warnings: list[str] = []

    # Prefer labeled values / form fields that match concepts.
    field_values, unresolved = extract_requested_values(
        pages=pages,
        instruction=instruction,
        concepts=concepts,
        include_entities=True,
    )

    values.extend(field_values)

    answer: str | None = None

    if values:
        parts = [
            f"{item.label}: {item.value}"
            for item in values[:8]
        ]
        answer = "; ".join(parts)
    else:
        # Fall back to the highest-signal text snippet per requested concept,
        # instead of stopping at the very first concept that matches.
        snippet_values: list[ExtractedValue] = []

        for concept in concepts:
            for page in pages:
                text = page.final_text or ""

                if not _concept_matches(concept, text):
                    continue

                snippet = _snippet(text, concept)
                snippet_values.append(
                    ExtractedValue(
                        label=concept,
                        value=snippet,
                        value_type="text",
                        confidence=0.55,
                        extraction_method="regex",
                        evidence=SourceEvidence(
                            page_number=page.page_number,
                            source_text=snippet,
                            source_reference=_source_reference(page),
                        ),
                    )
                )
                break

        values.extend(snippet_values)

        if snippet_values:
            answer = "; ".join(
                f"{item.label}: {item.value}" for item in snippet_values[:8]
            )

    if not answer:
        warnings.append(
            "Could not derive a confident answer from the selected pages."
        )

    return answer, values, unresolved, warnings


def extract_requested_values(
    *,
    pages: list[DocumentPage],
    instruction: str,
    concepts: list[str],
    include_entities: bool = True,
) -> tuple[list[ExtractedValue], list[str]]:
    values: list[ExtractedValue] = []
    unresolved: list[str] = []
    found_labels: set[str] = set()

    lower_instruction = instruction.lower()

    wants_emails = "email" in lower_instruction
    wants_phones = "phone" in lower_instruction
    wants_money = any(
        token in lower_instruction
        for token in ("money", "amount", "price", "cost", "dollar")
    )
    wants_dates = "date" in lower_instruction

    for page in pages:
        form_fields = _parse_json(page.form_fields_json)

        if isinstance(form_fields, dict):
            for key, value in form_fields.items():
                key_lower = str(key).lower()

                if concepts and not any(
                    _concept_matches(concept, key_lower, str(value))
                    for concept in concepts
                ):
                    continue

                label = str(key)
                values.append(
                    ExtractedValue(
                        label=label,
                        value=value,
                        value_type="identifier",
                        confidence=0.92,
                        extraction_method="form_field",
                        evidence=SourceEvidence(
                            page_number=page.page_number,
                            source_text=f"{key}: {value}",
                            source_reference=_source_reference(page),
                        ),
                    )
                )
                found_labels.add(label.lower())

        text = page.final_text or ""

        for concept in concepts:
            if _concept_matches(concept, *found_labels):
                continue

            label = _normalize_concept(concept)
            hit = find_label_value(text, label)

            if not hit:
                # Also try joining multi-token concepts already split.
                continue

            values.append(
                ExtractedValue(
                    label=label,
                    value=hit,
                    value_type="text",
                    confidence=0.8,
                    extraction_method="label_value",
                    evidence=SourceEvidence(
                        page_number=page.page_number,
                        source_text=_snippet(text, label),
                        source_reference=_source_reference(page),
                    ),
                )
            )
            found_labels.add(label.lower())

        if include_entities:
            entities = extract_generic_entities(text)

            if wants_emails or "email" in concepts:
                for email in entities["email"]:
                    values.append(
                        ExtractedValue(
                            label="email",
                            value=email,
                            value_type="email",
                            confidence=0.9,
                            extraction_method="regex",
                            evidence=SourceEvidence(
                                page_number=page.page_number,
                                source_text=email,
                                source_reference=_source_reference(page),
                            ),
                        )
                    )

            if wants_phones or "phone" in concepts:
                for phone in entities["phone"]:
                    values.append(
                        ExtractedValue(
                            label="phone",
                            value=phone,
                            value_type="phone",
                            confidence=0.85,
                            extraction_method="regex",
                            evidence=SourceEvidence(
                                page_number=page.page_number,
                                source_text=phone,
                                source_reference=_source_reference(page),
                            ),
                        )
                    )

            if wants_money:
                for amount in entities["money"]:
                    values.append(
                        ExtractedValue(
                            label="amount",
                            value=amount,
                            value_type="money",
                            confidence=0.75,
                            extraction_method="regex",
                            evidence=SourceEvidence(
                                page_number=page.page_number,
                                source_text=amount,
                                source_reference=_source_reference(page),
                            ),
                        )
                    )

            if wants_dates or "date" in concepts:
                for date in entities["date"]:
                    values.append(
                        ExtractedValue(
                            label="date",
                            value=date,
                            value_type="date",
                            confidence=0.8,
                            extraction_method="regex",
                            evidence=SourceEvidence(
                                page_number=page.page_number,
                                source_text=date,
                                source_reference=_source_reference(page),
                            ),
                        )
                    )

    # Multi-word label attempts from the original instruction.
    label_candidates = re.findall(
        r"(?:contract|solicitation|award|naics|ueid|caf|period of performance)"
        r"(?:\s+(?:number|code|date|rate|title))?",
        instruction,
        re.IGNORECASE,
    )

    for label in label_candidates:
        if label.lower() in found_labels:
            continue

        for page in pages:
            hit = find_label_value(page.final_text or "", label)

            if not hit:
                continue

            values.append(
                ExtractedValue(
                    label=label,
                    value=hit,
                    value_type="identifier",
                    confidence=0.84,
                    extraction_method="label_value",
                    evidence=SourceEvidence(
                        page_number=page.page_number,
                        source_text=_snippet(page.final_text or "", label),
                        source_reference=_source_reference(page),
                    ),
                )
            )
            found_labels.add(label.lower())
            break

    for concept in concepts:
        if concept in {
            "email",
            "emails",
            "phone",
            "phones",
            "date",
            "dates",
            "table",
            "tables",
        }:
            continue

        if not _concept_matches(concept, *found_labels):
            unresolved.append(concept)

    return values, unresolved


def _finalize_values(
    values: list[ExtractedValue],
) -> list[ExtractedValue]:
    seen: set[tuple[str, str, int]] = set()
    unique: list[ExtractedValue] = []

    for value in values:
        key = (
            value.label.lower(),
            str(value.value),
            value.evidence.page_number,
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(value)

    return sorted(unique, key=lambda item: item.confidence, reverse=True)


async def execute_extraction(
    *,
    document_id: str,
    instruction: str,
    pages: list[DocumentPage],
    intent: ExtractionIntent,
) -> UniversalExtractionResponse:

    pages_used = [page.page_number for page in pages]
    warnings: list[str] = []
    unresolved: list[str] = []

    answer: str | None = None
    values: list[ExtractedValue] = []
    tables: list[ExtractedTable] = []

    if not pages:
        return UniversalExtractionResponse(
            document_id=document_id,
            instruction=instruction,
            intent=intent.mode,
            answer=None,
            values=[],
            tables=[],
            pages_used=[],
            unresolved_requests=intent.requested_concepts,
            warnings=[
                "No relevant pages were selected for this request."
            ],
        )

    if intent.mode == "table":
        tables, table_warnings = extract_requested_tables(
            pages=pages,
            instruction=instruction,
            concepts=intent.requested_concepts,
        )
        warnings.extend(table_warnings)

        if intent.requested_concepts and not tables:
            unresolved = list(intent.requested_concepts)

    elif intent.mode == "question":
        answer, values, unresolved, question_warnings = answer_from_pages(
            pages=pages,
            instruction=instruction,
            concepts=intent.requested_concepts,
        )
        warnings.extend(question_warnings)

    elif intent.mode == "summary":
        # Deterministic summary: top snippets + key form fields.
        values, unresolved = extract_requested_values(
            pages=pages,
            instruction=instruction,
            concepts=intent.requested_concepts,
            include_entities=True,
        )

        snippets = [
            (page.final_text or "")[:280].strip()
            for page in pages[:3]
            if (page.final_text or "").strip()
        ]

        answer = " ".join(snippets) if snippets else None

        if not answer:
            warnings.append("No summary text was available.")

    else:
        values, unresolved = extract_requested_values(
            pages=pages,
            instruction=instruction,
            concepts=intent.requested_concepts,
        )

        if not values:
            warnings.append(
                "No matching values were found for the requested fields."
            )

    return UniversalExtractionResponse(
        document_id=document_id,
        instruction=instruction,
        intent=intent.mode,
        answer=answer,
        values=_finalize_values(values),
        tables=tables,
        pages_used=pages_used,
        unresolved_requests=unresolved,
        warnings=warnings,
    )
