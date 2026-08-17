import re
from dataclasses import dataclass
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
EXACT_NUMBER_CONFIDENCE = 0.95


@dataclass(frozen=True)
class DetectedRelationshipMatch:
    parent_document_id: str
    relationship_type: str
    confidence: float
    matched_on: Literal["contract_number", "contract_title"]


def _candidate_numbers(text: str) -> list[str]:
    return list(dict.fromkeys(CONTRACT_NUMBER_PATTERN.findall(text)))


def _candidate_title_phrases(text: str) -> list[str]:
    return list(
        dict.fromkeys(
            match.strip()
            for match in REFERENCE_PHRASE_PATTERN.findall(text)
        )
    )


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

    if number_candidates:
        other_number_fields = list(
            database.scalars(
                select(DocumentMetadataField).where(
                    DocumentMetadataField.field_key
                    == "contract_number",
                    DocumentMetadataField.document_id != document.id,
                )
            )
        )

        for candidate in number_candidates:
            for field in other_number_fields:
                if (
                    field.value.strip().upper()
                    == candidate.strip().upper()
                ):
                    return DetectedRelationshipMatch(
                        parent_document_id=field.document_id,
                        relationship_type=relationship_type,
                        confidence=EXACT_NUMBER_CONFIDENCE,
                        matched_on="contract_number",
                    )

    title_candidates = _candidate_title_phrases(full_text)

    if not title_candidates:
        return None

    other_title_fields = list(
        database.scalars(
            select(DocumentMetadataField).where(
                DocumentMetadataField.field_key == "contract_title",
                DocumentMetadataField.document_id != document.id,
            )
        )
    )

    best_score = 0.0
    best_field: DocumentMetadataField | None = None

    for field in other_title_fields:
        for candidate in title_candidates:
            score = SequenceMatcher(
                None,
                candidate.lower(),
                field.value.lower(),
            ).ratio()

            if score > best_score:
                best_score = score
                best_field = field

    if best_field is None or best_score < TITLE_MATCH_THRESHOLD:
        return None

    # Map the [threshold, 1.0] similarity range onto a [0.5, 0.85]
    # confidence band — fuzzy title matches are never as certain as an
    # exact contract-number match.
    span = 1 - TITLE_MATCH_THRESHOLD
    confidence = 0.5 + (best_score - TITLE_MATCH_THRESHOLD) / span * 0.35

    return DetectedRelationshipMatch(
        parent_document_id=best_field.document_id,
        relationship_type=relationship_type,
        confidence=round(confidence, 2),
        matched_on="contract_title",
    )
