"""document → detected family → staging profile, pinned with its version.

Signals, in order:
  1. Deterministic keyword family classification of the document's text
     (structure_detection.classify_document_family — no AI).
  2. When that is inconclusive, the document's existing AI classification
     (Document.document_type), if one was recorded.
  3. When still inconclusive, structural evidence the canonical pipeline
     already found: an incorporated-clause listing plus a contract number
     is a government contract.

The profile is whichever registered profile claims the family; otherwise
the generic profile. A document is never forced into a profile whose
family it wasn't detected as (an invoice never becomes contract_v3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_clause_reference import DocumentClauseReference
from app.models.document_contract_summary import DocumentContractSummary
from app.models.document_page import DocumentPage
from app.models.document_staging_workbook import DocumentStagingWorkbook
from app.services.structure_detection import (
    DOCUMENT_FAMILIES,
    classify_document_family,
    family_for_document_type,
)
from app.staging import registry
from app.staging.profile import StagingProfile

_CLASSIFY_PAGE_LIMIT = 10
_MIN_CLAUSE_LISTINGS = 5
_INCONCLUSIVE = {"unknown", "generic_business"}


@dataclass
class ProfileResolution:
    profile: StagingProfile
    family: str
    family_label: str
    reasons: list[str] = field(default_factory=list)


def _page_text(database: Session, document_id: str) -> str:
    pages = database.scalars(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
        .limit(_CLASSIFY_PAGE_LIMIT)
    )
    return "\n".join(page.final_text or "" for page in pages)


def _has_contract_structure(database: Session, document_id: str) -> bool:
    listings = database.scalar(
        select(func.count())
        .select_from(DocumentClauseReference)
        .where(
            DocumentClauseReference.document_id == document_id,
            DocumentClauseReference.citation_context == "listing",
        )
    )
    contract_number = database.scalar(
        select(DocumentContractSummary.contract_number).where(
            DocumentContractSummary.document_id == document_id
        )
    )
    return (listings or 0) >= _MIN_CLAUSE_LISTINGS and bool(contract_number)


def resolve_profile(database: Session, document: Document) -> ProfileResolution:
    reasons: list[str] = []
    family, label, confidence = classify_document_family(_page_text(database, document.id))
    reasons.append(f"Keyword classification: {label} (confidence {confidence:.2f}).")

    if family in _INCONCLUSIVE and document.document_type:
        mapped, mapped_label = family_for_document_type(
            document.document_type, document.classification_confidence or 0.0
        )
        if mapped not in _INCONCLUSIVE:
            family, label = mapped, mapped_label
            reasons.append(f"AI document classification: {document.document_type}.")

    if family in _INCONCLUSIVE and _has_contract_structure(database, document.id):
        family = "government_contract"
        label = DOCUMENT_FAMILIES[family][0]
        reasons.append(
            "Structural evidence: incorporated-clause listing and a contract number."
        )

    profile = registry.profile_for_family(family)
    if profile is None:
        profile = registry.generic_profile()
        if family not in _INCONCLUSIVE:
            reasons.append(
                f"No staging profile is registered for '{label}' yet; using the "
                f"{profile.display_name} profile."
            )
    else:
        reasons.append(f"{profile.display_name} profile is registered for '{label}'.")

    return ProfileResolution(profile=profile, family=family, family_label=label, reasons=reasons)


def resolve_and_persist_profile(
    database: Session, document: Document
) -> DocumentStagingWorkbook:
    """(Re)pins the document's staging profile. Called when extraction runs;
    commits."""

    resolution = resolve_profile(database, document)
    record = database.scalars(
        select(DocumentStagingWorkbook).where(DocumentStagingWorkbook.document_id == document.id)
    ).first()
    if record is None:
        record = DocumentStagingWorkbook(document_id=document.id)
        database.add(record)
    record.profile_id = resolution.profile.profile_id
    record.profile_version = resolution.profile.profile_version
    record.document_family = resolution.family
    record.document_family_label = resolution.family_label
    record.resolution_reasons = resolution.reasons
    record.resolved_at = datetime.now(timezone.utc)
    database.commit()
    return record
