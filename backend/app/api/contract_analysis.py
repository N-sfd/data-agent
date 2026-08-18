from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.dependencies import get_database
from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.models.document_page import DocumentPage
from app.models.metadata_field_audit_log import MetadataFieldAuditLog
from app.models.extraction_model import ExtractionField
from app.schemas.contract_analysis import (
    AcceptAllRequest,
    AnalyzeContractRequest,
    ApproveDocumentRequest,
    ApproveDocumentResponse,
    ChildRelationship,
    ChildRelationshipsResponse,
    ConfirmRelationshipRequest,
    ConfirmRelationshipResponse,
    ContractAnalysisResponse,
    ContractClassification,
    DetectedRelationship,
    FieldAuditEntry,
    FieldReviewRequest,
    MetadataFieldResult,
)
from app.schemas.contract_clauses import ClauseExtractionResponse
from app.schemas.contract_signatures import (
    SignatureExtractionResponse,
)
from app.schemas.contract_tables import TableExtractionResponse
from app.services.ai_provider import AIProviderError
from app.services.ai_provider_factory import create_ai_provider
from app.services.contract_classifier import classify_contract
from app.services.contract_field_schema import FieldSpec
from app.services.contract_clause_extractor import (
    clause_to_result,
    extract_contract_clauses,
    get_document_clauses,
)
from app.services.contract_metadata_extractor import (
    extract_contract_metadata,
    field_to_result,
    get_metadata_field,
)
from app.services.contract_signature_extractor import (
    extract_contract_signatures,
    get_document_signatures,
    signature_to_result,
)
from app.services.contract_structured_output import (
    build_structured_output,
)
from app.services.contract_table_extractor import (
    normalize_document_tables,
)
from app.services.dashboard_stats import compute_document_status
from app.services.relationship_detector import (
    DetectedRelationshipMatch,
    detect_relationship,
)

router = APIRouter()
settings = get_settings()


def _load_ready_document(
    database: Session, document_id: str
) -> Document:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if document.processing_status not in {
        "completed",
        "completed_with_warnings",
    }:
        raise HTTPException(
            status_code=409,
            detail="Run page extraction before analyzing the contract.",
        )

    return document


def _load_pages(
    database: Session, document_id: str
) -> list[DocumentPage]:
    return list(
        database.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
    )


def _build_relationship_response(
    database: Session,
    match: DetectedRelationshipMatch,
    *,
    status: str = "pending",
) -> DetectedRelationship:
    parent = database.get(Document, match.parent_document_id)

    parent_title = (
        parent.original_filename if parent else "Unknown document"
    )

    title_field = get_metadata_field(
        database,
        document_id=match.parent_document_id,
        field_key="contract_title",
    )

    if title_field and title_field.value:
        parent_title = title_field.value

    number_field = get_metadata_field(
        database,
        document_id=match.parent_document_id,
        field_key="contract_number",
    )

    return DetectedRelationship(
        parent_document_id=match.parent_document_id,
        parent_document_title=parent_title,
        parent_document_number=(
            number_field.value if number_field else None
        ),
        relationship_type=match.relationship_type,
        confidence=match.confidence,
        matched_on=match.matched_on,
        status=status,
    )


def _relationship_match_from_document(
    document: Document,
) -> DetectedRelationshipMatch | None:
    if (
        document.parent_document_id is None
        or document.parent_relationship_status is None
    ):
        return None

    return DetectedRelationshipMatch(
        parent_document_id=document.parent_document_id,
        relationship_type=document.parent_relationship_type or "",
        confidence=document.parent_relationship_confidence or 0.0,
        matched_on=(
            document.parent_relationship_matched_on
            or "contract_number"
        ),
    )


@router.post(
    "/{document_id}/analyze-contract",
    response_model=ContractAnalysisResponse,
)
async def analyze_contract(
    document_id: str,
    payload: AnalyzeContractRequest | None = None,
    database: Session = Depends(get_database),
) -> ContractAnalysisResponse:
    document = _load_ready_document(database, document_id)
    pages = _load_pages(database, document_id)

    warnings: list[str] = []

    if not pages:
        warnings.append(
            "No extracted pages were found for this document."
        )

    extra_field_specs: list[FieldSpec] = []

    if payload and payload.extraction_model_id is not None:
        custom_fields = list(
            database.scalars(
                select(ExtractionField).where(
                    ExtractionField.model_id
                    == payload.extraction_model_id
                )
            )
        )

        extra_field_specs = [
            FieldSpec(
                group="Custom",
                key=f"custom_{field.id}",
                label=field.field_name,
                description=field.description,
                data_type=field.data_type,
            )
            for field in custom_fields
        ]

    ai_provider = create_ai_provider(settings)

    try:
        classification = await classify_contract(
            pages=pages,
            ai_provider=ai_provider,
        )
    except AIProviderError as exc:
        warnings.append(f"Classification unavailable: {exc}")
        classification = ContractClassification()

    document.document_type = classification.document_type
    document.industry = classification.industry
    document.contract_side = classification.contract_side
    document.document_language = classification.language
    document.classification_confidence = classification.confidence
    database.commit()

    metadata_fields = await extract_contract_metadata(
        database=database,
        document=document,
        pages=pages,
        ai_provider=ai_provider,
        extra_field_specs=extra_field_specs,
    )

    relationship_response: DetectedRelationship | None = None
    match = detect_relationship(
        database=database,
        document=document,
        pages=pages,
    )

    if match is not None:
        document.parent_document_id = match.parent_document_id
        document.parent_relationship_type = match.relationship_type
        document.parent_relationship_confidence = match.confidence
        document.parent_relationship_matched_on = match.matched_on
        document.parent_relationship_status = "pending"
        database.commit()

        relationship_response = _build_relationship_response(
            database, match, status="pending"
        )

    return ContractAnalysisResponse(
        document_id=document.id,
        classification=classification,
        metadata_fields=metadata_fields,
        relationship=relationship_response,
        warnings=warnings,
    )


@router.get(
    "/{document_id}/analyze-contract",
    response_model=ContractAnalysisResponse,
)
async def get_contract_analysis(
    document_id: str,
    database: Session = Depends(get_database),
) -> ContractAnalysisResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if document.document_type is None:
        raise HTTPException(
            status_code=404,
            detail="This document has not been analyzed yet.",
        )

    classification = ContractClassification(
        document_type=document.document_type,
        industry=document.industry,
        contract_side=document.contract_side or "unknown",
        language=document.document_language,
        confidence=document.classification_confidence or 0.0,
    )

    fields = list(
        database.scalars(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id
            )
        )
    )

    relationship = None
    match = _relationship_match_from_document(document)

    if match is not None:
        relationship = _build_relationship_response(
            database,
            match,
            status=document.parent_relationship_status or "pending",
        )

    return ContractAnalysisResponse(
        document_id=document.id,
        classification=classification,
        metadata_fields=[
            field_to_result(field) for field in fields
        ],
        relationship=relationship,
        warnings=[],
    )


@router.post(
    "/{document_id}/confirm-relationship",
    response_model=ConfirmRelationshipResponse,
)
async def confirm_relationship(
    document_id: str,
    payload: ConfirmRelationshipRequest,
    database: Session = Depends(get_database),
) -> ConfirmRelationshipResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if (
        document.parent_document_id is None
        or document.parent_relationship_status != "pending"
    ):
        raise HTTPException(
            status_code=409,
            detail="No pending relationship to resolve for this document.",
        )

    if payload.action == "confirm":
        document.parent_relationship_status = "confirmed"
        database.commit()

        match = _relationship_match_from_document(document)
        assert match is not None

        relationship = _build_relationship_response(
            database, match, status="confirmed"
        )

        return ConfirmRelationshipResponse(
            document_id=document.id,
            status="confirmed",
            relationship=relationship,
        )

    document.parent_relationship_status = "rejected"
    document.parent_document_id = None
    database.commit()

    return ConfirmRelationshipResponse(
        document_id=document.id,
        status="rejected",
        relationship=None,
    )


@router.get(
    "/{document_id}/child-relationships",
    response_model=ChildRelationshipsResponse,
)
async def get_child_relationships(
    document_id: str,
    database: Session = Depends(get_database),
) -> ChildRelationshipsResponse:
    parent = database.get(Document, document_id)

    if parent is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    child_documents = list(
        database.scalars(
            select(Document).where(
                Document.parent_document_id == document_id
            )
        )
    )

    children: list[ChildRelationship] = []

    for child in child_documents:
        title_field = get_metadata_field(
            database,
            document_id=child.id,
            field_key="contract_title",
        )
        number_field = get_metadata_field(
            database,
            document_id=child.id,
            field_key="contract_number",
        )

        children.append(
            ChildRelationship(
                child_document_id=child.id,
                child_document_title=(
                    title_field.value
                    if title_field and title_field.value
                    else child.original_filename
                ),
                child_document_number=(
                    number_field.value if number_field else None
                ),
                relationship_type=child.parent_relationship_type
                or "",
                confidence=child.parent_relationship_confidence
                or 0.0,
                status=child.parent_relationship_status
                or "pending",
            )
        )

    return ChildRelationshipsResponse(
        parent_document_id=document_id,
        children=children,
    )


@router.post(
    "/{document_id}/approve",
    response_model=ApproveDocumentResponse,
)
async def approve_document(
    document_id: str,
    payload: ApproveDocumentRequest,
    database: Session = Depends(get_database),
) -> ApproveDocumentResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if compute_document_status(database, document) != "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                "This document isn't ready to approve yet — it must "
                "be classified and every extracted field must be "
                "reviewed first."
            ),
        )

    document.approved_by = payload.changed_by
    document.approved_at = datetime.now(timezone.utc)
    database.commit()

    return ApproveDocumentResponse(
        document_id=document.id,
        approved_by=document.approved_by,
        approved_at=document.approved_at,
    )


@router.get(
    "/{document_id}/structured-output",
)
async def get_structured_output(
    document_id: str,
    database: Session = Depends(get_database),
) -> dict[str, Any]:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    fields = list(
        database.scalars(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id
            )
        )
    )

    if not fields:
        raise HTTPException(
            status_code=404,
            detail=(
                "No structured metadata found for this document. "
                "Run contract analysis first."
            ),
        )

    return build_structured_output(fields)


_ACTION_TO_STATUS: dict[str, str] = {
    "accept": "accepted",
    "edit": "edited",
    "reject": "rejected",
    "mark_unknown": "unknown",
}


@router.post(
    "/{document_id}/metadata-fields/{field_key}/review",
    response_model=MetadataFieldResult,
)
async def review_metadata_field(
    document_id: str,
    field_key: str,
    payload: FieldReviewRequest,
    database: Session = Depends(get_database),
) -> MetadataFieldResult:
    field = get_metadata_field(
        database,
        document_id=document_id,
        field_key=field_key,
    )

    if field is None:
        raise HTTPException(
            status_code=404,
            detail="Metadata field not found.",
        )

    if payload.action == "edit" and not payload.value:
        raise HTTPException(
            status_code=400,
            detail="A value is required to edit a field.",
        )

    previous_value = field.value
    new_value = (
        payload.value if payload.action == "edit" else field.value
    )

    if payload.action == "edit":
        field.value = payload.value or ""

    field.review_status = _ACTION_TO_STATUS[payload.action]

    database.add(
        MetadataFieldAuditLog(
            document_id=document_id,
            field_key=field_key,
            action=payload.action,
            previous_value=previous_value,
            new_value=new_value,
            changed_by=payload.changed_by,
        )
    )

    database.commit()

    return field_to_result(field)


@router.post(
    "/{document_id}/metadata-fields/accept-all",
    response_model=list[MetadataFieldResult],
)
async def accept_all_metadata_fields(
    document_id: str,
    payload: AcceptAllRequest,
    database: Session = Depends(get_database),
) -> list[MetadataFieldResult]:
    fields = list(
        database.scalars(
            select(DocumentMetadataField).where(
                DocumentMetadataField.document_id == document_id
            )
        )
    )

    if not fields:
        raise HTTPException(
            status_code=404,
            detail="No metadata fields found for this document.",
        )

    for field in fields:
        if field.review_status != "pending":
            continue

        field.review_status = "accepted"

        database.add(
            MetadataFieldAuditLog(
                document_id=document_id,
                field_key=field.field_key,
                action="accept",
                previous_value=field.value,
                new_value=field.value,
                changed_by=payload.changed_by,
            )
        )

    database.commit()

    return [field_to_result(field) for field in fields]


@router.get(
    "/{document_id}/metadata-fields/{field_key}/audit-log",
    response_model=list[FieldAuditEntry],
)
async def get_field_audit_log(
    document_id: str,
    field_key: str,
    database: Session = Depends(get_database),
) -> list[FieldAuditEntry]:
    entries = list(
        database.scalars(
            select(MetadataFieldAuditLog)
            .where(
                MetadataFieldAuditLog.document_id == document_id,
                MetadataFieldAuditLog.field_key == field_key,
            )
            .order_by(MetadataFieldAuditLog.changed_at.desc())
        )
    )

    return [
        FieldAuditEntry(
            action=entry.action,
            previous_value=entry.previous_value,
            new_value=entry.new_value,
            changed_by=entry.changed_by,
            changed_at=entry.changed_at,
        )
        for entry in entries
    ]


@router.post(
    "/{document_id}/extract-clauses",
    response_model=ClauseExtractionResponse,
)
async def extract_clauses(
    document_id: str,
    database: Session = Depends(get_database),
) -> ClauseExtractionResponse:
    document = _load_ready_document(database, document_id)
    pages = _load_pages(database, document_id)

    ai_provider = create_ai_provider(settings)

    clauses, warnings = await extract_contract_clauses(
        database=database,
        document=document,
        pages=pages,
        ai_provider=ai_provider,
    )

    return ClauseExtractionResponse(
        document_id=document.id,
        clauses=clauses,
        warnings=warnings,
    )


@router.get(
    "/{document_id}/extract-clauses",
    response_model=ClauseExtractionResponse,
)
async def get_extracted_clauses(
    document_id: str,
    database: Session = Depends(get_database),
) -> ClauseExtractionResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    clauses = get_document_clauses(database, document_id)

    return ClauseExtractionResponse(
        document_id=document.id,
        clauses=[clause_to_result(clause) for clause in clauses],
        warnings=[],
    )


@router.post(
    "/{document_id}/extract-tables",
    response_model=TableExtractionResponse,
)
async def extract_tables(
    document_id: str,
    database: Session = Depends(get_database),
) -> TableExtractionResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    pages = _load_pages(database, document_id)

    tables = normalize_document_tables(
        pages, document.original_filename
    )

    return TableExtractionResponse(
        document_id=document.id,
        tables=tables,
    )


@router.post(
    "/{document_id}/extract-signatures",
    response_model=SignatureExtractionResponse,
)
async def extract_signatures(
    document_id: str,
    database: Session = Depends(get_database),
) -> SignatureExtractionResponse:
    document = _load_ready_document(database, document_id)
    pages = _load_pages(database, document_id)

    ai_provider = create_ai_provider(settings)

    signatures, warnings = await extract_contract_signatures(
        database=database,
        document=document,
        pages=pages,
        ai_provider=ai_provider,
    )

    return SignatureExtractionResponse(
        document_id=document.id,
        signatures=signatures,
        warnings=warnings,
    )


@router.get(
    "/{document_id}/extract-signatures",
    response_model=SignatureExtractionResponse,
)
async def get_extracted_signatures(
    document_id: str,
    database: Session = Depends(get_database),
) -> SignatureExtractionResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    signatures = get_document_signatures(database, document_id)

    return SignatureExtractionResponse(
        document_id=document.id,
        signatures=[
            signature_to_result(signature)
            for signature in signatures
        ],
        warnings=[],
    )
