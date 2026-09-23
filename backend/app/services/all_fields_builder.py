"""V3 All Fields builder (docs/v3-schema-manifest.md §1).

Reuses the existing `document_metadata_fields` storage layer (gap analysis:
"the one dataset the old pipeline already does reasonably well at the
storage layer — the problem is entirely upstream, in what gets classified
as a candidate"). What changes here is the SOURCE of candidates:
GENERAL_ACCEPTED_FIELD-category `ClassifiedCandidate`s from the new
structure_classifier/candidate_router pipeline, not the old kv_* schema-
discovery stream — this is what keeps TOC lines, subsection-number
fragments, and table scaffolding out of All Fields (docs/source-to-v3-
mapping.md's confirmed root cause).

Rows are written with `extraction_source="v3"`, a new, third value
alongside the existing "contract"/"target" sources — additive, the old
sources are untouched.
"""

from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.schemas.candidate_classification import ClassifiedCandidate

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    slug = _SLUG_RE.sub("_", text.strip().lower()).strip("_")
    return slug or "field"


def _extraction_method_for(candidate: ClassifiedCandidate) -> str:
    # Vocabulary per docs/v3-implementation-plan.md decision #6. Every
    # candidate reaching All Fields came from deterministic geometry/text
    # classification, never AI, by construction of this pipeline.
    if candidate.region_type == "TABLE_ROW":
        return "table"
    if candidate.region_type == "FORM_FIELD_VALUE":
        return "form_field"
    if candidate.extraction_method == "ocr":
        return "ocr"
    return "native_text"


def build_all_fields(
    *, document: Document, candidates: list[ClassifiedCandidate]
) -> list[DocumentMetadataField]:
    rows: list[DocumentMetadataField] = []
    seen: set[tuple[str, str]] = set()

    for candidate in candidates:
        if candidate.category != "GENERAL_ACCEPTED_FIELD" or not candidate.value:
            continue
        label = (candidate.label or candidate.value).strip()
        value = candidate.value.strip()
        if not label or not value:
            continue
        dedupe_key = (label.lower(), value.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        qa_status = "Verified" if candidate.confidence >= 0.7 else "Needs Review"

        rows.append(
            DocumentMetadataField(
                document_id=document.id,
                field_group="General",
                field_key=f"v3_{_slug(label)}",
                label=label,
                value=value,
                confidence=candidate.confidence,
                extraction_method=_extraction_method_for(candidate),
                evidence_json={
                    "page_number": candidate.source_page,
                    "source_text": candidate.evidence,
                    "category": "General",
                    "qa_status": qa_status,
                    "reason_codes": candidate.reason_codes,
                },
                review_status="pending",
                original_value=value,
                extraction_source="v3",
            )
        )

    return rows


def persist_all_fields(
    *, database: Session, document_id: str, rows: list[DocumentMetadataField]
) -> None:
    database.execute(
        delete(DocumentMetadataField).where(
            DocumentMetadataField.document_id == document_id,
            DocumentMetadataField.extraction_source == "v3",
        )
    )
    for row in rows:
        database.add(row)
