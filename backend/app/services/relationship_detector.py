import re
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.models.document_page import DocumentPage

CONTRACT_NUMBER_PATTERN = re.compile(
    r"\b[A-Z]{2,6}-\d{4}-\d{3,6}\b"
)

# A phrase like "pursuant to the Master Services Agreement" or
# "Amendment to the Acme Supplier Agreement" — captures the referenced
# agreement's title for a fuzzy match against other documents.
REFERENCE_PHRASE_PATTERN = re.compile(
    r"(?:pursuant to|amendment to|amends|under|in accordance with)\s+"
    r"(?:the\s+)?"
    r"([A-Z][A-Za-z0-9,'&\-\s]{5,80}"
    r"(?:Agreement|Contract|MSA|SOW))",
)

# Document types that plausibly have a parent contract, mapped to the
# relationship label recorded when a parent is found.
PARENT_RELATIONSHIP_TYPES: dict[str, str] = {
    "Amendment": "amendment_of",
    "Change Order": "change_order_of",
    "Statement of Work": "sow_of",
    "Subcontract": "subcontract_of",
}

TITLE_MATCH_THRESHOLD = 0.6

# Weighted signal points, normalized to a 0-100 (0-1.0) confidence
# score. An exact contract-number match is weighted highest since a
# contract number is effectively a unique identifier; the others
# corroborate rather than independently establish the relationship.
POINTS_CONTRACT_NUMBER = 70
POINTS_EXPLICIT_REFERENCE = 15
POINTS_COUNTERPARTY = 7
POINTS_COMPATIBLE_TYPE = 5
POINTS_DATE_RANGE = 3

BONUS_SIGNAL_FIELD_KEYS = ("supplier", "customer", "effective_date")


@dataclass(frozen=True)
class DetectedRelationshipMatch:
    parent_document_id: str
    relationship_type: str
    confidence: float
    matched_on: Literal["contract_number", "contract_title"]
    reasons: list[str] = field(default_factory=list)
    detection_method: str = "automatic"


def _candidate_numbers(text: str) -> list[str]:
    return list(dict.fromkeys(CONTRACT_NUMBER_PATTERN.findall(text)))


def _candidate_title_phrases(text: str) -> list[str]:
    return list(
        dict.fromkeys(
            match.strip()
            for match in REFERENCE_PHRASE_PATTERN.findall(text)
        )
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def detect_relationship(
    *,
    database: Session,
    document: Document,
    pages: list[DocumentPage],
) -> DetectedRelationshipMatch | None:
    relationship_type = PARENT_RELATIONSHIP_TYPES.get(
        document.document_type or ""
    )

    if relationship_type is None:
        return None

    full_text = "\n".join(
        page.final_text or "" for page in pages
    )

    number_candidates = _candidate_numbers(full_text)
    title_candidates = _candidate_title_phrases(full_text)

    if not number_candidates and not title_candidates:
        return None

    # Find candidates via targeted SQL first — a handful of documents
    # at most — rather than scoring every document in the database.
    candidate_ids: set[str] = set()

    if number_candidates:
        number_matches = database.execute(
            select(
                DocumentMetadataField.document_id,
                DocumentMetadataField.value,
            ).where(
                DocumentMetadataField.field_key == "contract_number",
                DocumentMetadataField.document_id != document.id,
            )
        ).all()

        matched_numbers = {n.upper() for n in number_candidates}
        candidate_ids.update(
            doc_id
            for doc_id, value in number_matches
            if value and value.strip().upper() in matched_numbers
        )

    if title_candidates:
        title_matches = database.execute(
            select(
                DocumentMetadataField.document_id,
                DocumentMetadataField.value,
            ).where(
                DocumentMetadataField.field_key == "contract_title",
                DocumentMetadataField.document_id != document.id,
            )
        ).all()

        for doc_id, title in title_matches:
            if not title:
                continue

            for phrase in title_candidates:
                ratio = SequenceMatcher(
                    None, phrase.lower(), title.lower()
                ).ratio()

                if ratio >= TITLE_MATCH_THRESHOLD:
                    candidate_ids.add(doc_id)
                    break

    if not candidate_ids:
        return None

    candidates = {
        c.id: c
        for c in database.scalars(
            select(Document).where(Document.id.in_(candidate_ids))
        )
    }

    # Batch-fetch bonus-signal fields for the child document plus every
    # remaining candidate in one query instead of per-candidate calls.
    field_rows = database.execute(
        select(
            DocumentMetadataField.document_id,
            DocumentMetadataField.field_key,
            DocumentMetadataField.value,
        ).where(
            DocumentMetadataField.document_id.in_(
                candidate_ids | {document.id}
            ),
            DocumentMetadataField.field_key.in_(
                BONUS_SIGNAL_FIELD_KEYS
                + ("contract_number", "contract_title")
            ),
        )
    ).all()

    field_values: dict[tuple[str, str], str] = {
        (doc_id, key): value
        for doc_id, key, value in field_rows
        if value
    }

    def value_for(doc_id: str, key: str) -> str | None:
        return field_values.get((doc_id, key))

    matched_numbers = {n.upper() for n in number_candidates}
    child_date = _parse_date(value_for(document.id, "effective_date"))

    best_score = 0.0
    best_candidate_id: str | None = None
    best_reasons: list[str] = []
    best_matched_on: Literal["contract_number", "contract_title"] = (
        "contract_title"
    )

    for candidate_id, candidate in candidates.items():
        score = 0.0
        reasons: list[str] = []
        matched_on: Literal["contract_number", "contract_title"] = (
            "contract_title"
        )

        candidate_number = value_for(candidate_id, "contract_number")
        candidate_title = value_for(candidate_id, "contract_title")

        number_matched = bool(
            candidate_number
            and candidate_number.strip().upper() in matched_numbers
        )

        if number_matched:
            score += POINTS_CONTRACT_NUMBER
            reasons.append("Matching contract number")
            matched_on = "contract_number"

        reference_matched = False

        if candidate_title:
            for phrase in title_candidates:
                ratio = SequenceMatcher(
                    None, phrase.lower(), candidate_title.lower()
                ).ratio()

                if ratio >= TITLE_MATCH_THRESHOLD:
                    reference_matched = True
                    break

        if reference_matched:
            score += POINTS_EXPLICIT_REFERENCE
            reasons.append("Explicit agreement reference")

            if not number_matched:
                matched_on = "contract_title"

        if not number_matched and not reference_matched:
            continue

        child_supplier = value_for(document.id, "supplier")
        child_customer = value_for(document.id, "customer")
        parent_supplier = value_for(candidate_id, "supplier")
        parent_customer = value_for(candidate_id, "customer")

        counterparty_matched = bool(
            (child_supplier and child_supplier == parent_supplier)
            or (child_customer and child_customer == parent_customer)
        )

        if counterparty_matched:
            score += POINTS_COUNTERPARTY
            reasons.append("Same counterparty")

        # The candidate looks like a "base" agreement rather than
        # another supporting document — a plausible parent type.
        if candidate.document_type not in PARENT_RELATIONSHIP_TYPES:
            score += POINTS_COMPATIBLE_TYPE
            reasons.append("Compatible document type")

        parent_date = _parse_date(value_for(candidate_id, "effective_date"))

        if child_date and parent_date and child_date >= parent_date:
            score += POINTS_DATE_RANGE
            reasons.append("Compatible date range")

        if score > best_score:
            best_score = score
            best_candidate_id = candidate_id
            best_reasons = reasons
            best_matched_on = matched_on

    if best_candidate_id is None or best_score <= 0:
        return None

    return DetectedRelationshipMatch(
        parent_document_id=best_candidate_id,
        relationship_type=relationship_type,
        confidence=round(min(best_score, 100.0) / 100, 2),
        matched_on=best_matched_on,
        reasons=best_reasons,
        detection_method="automatic",
    )
