from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.universal_extraction import SourceEvidence


ReviewStatusLiteral = Literal[
    "pending",
    "accepted",
    "edited",
    "rejected",
    "unknown",
]

ReviewActionLiteral = Literal[
    "accept",
    "edit",
    "reject",
    "mark_unknown",
]


DocumentTypeLiteral = Literal[
    "Master Services Agreement",
    "NDA",
    "Supplier Agreement",
    "Purchase Agreement",
    "Professional Services Agreement",
    "Software Agreement",
    "SaaS Agreement",
    "Lease",
    "Statement of Work",
    "Amendment",
    "Change Order",
    "Purchase Order",
    "Service Level Agreement",
    "License Agreement",
    "Consulting Agreement",
    "Construction Agreement",
    "Government Contract",
    "Subcontract",
    "Other",
]


class ContractClassification(BaseModel):
    document_type: DocumentTypeLiteral = "Other"

    industry: str | None = None

    contract_side: Literal[
        "buy_side",
        "sell_side",
        "unknown",
    ] = "unknown"

    language: str | None = None

    confidence: float = Field(
        default=0.0,
        ge=0,
        le=1,
    )


class MetadataFieldResult(BaseModel):
    field_group: str
    field_key: str
    label: str

    value: str

    confidence: float = Field(ge=0, le=1)

    extraction_method: Literal[
        "label_value",
        "regex",
        "ai",
    ]

    evidence: SourceEvidence

    verified: bool = False

    review_status: ReviewStatusLiteral = "pending"

    original_value: str = ""


class FieldReviewRequest(BaseModel):
    action: ReviewActionLiteral

    value: str | None = None

    changed_by: str = Field(min_length=1, max_length=120)


class AcceptAllRequest(BaseModel):
    changed_by: str = Field(min_length=1, max_length=120)


class FieldAuditEntry(BaseModel):
    action: ReviewActionLiteral

    previous_value: str | None = None
    new_value: str | None = None

    changed_by: str
    changed_at: datetime


class GlobalAuditEntry(BaseModel):
    document_id: str
    document_filename: str
    field_key: str

    action: ReviewActionLiteral

    previous_value: str | None = None
    new_value: str | None = None

    changed_by: str
    changed_at: datetime


class GlobalAuditLogResponse(BaseModel):
    entries: list[GlobalAuditEntry]
    total: int


class DetectedRelationship(BaseModel):
    parent_document_id: str
    parent_document_title: str
    parent_document_number: str | None = None

    relationship_type: str

    confidence: float = Field(ge=0, le=1)

    matched_on: Literal[
        "contract_number",
        "contract_title",
    ]

    status: Literal[
        "pending",
        "confirmed",
        "rejected",
    ] = "pending"


class ContractAnalysisResponse(BaseModel):
    document_id: str

    classification: ContractClassification

    metadata_fields: list[MetadataFieldResult]

    relationship: DetectedRelationship | None = None

    warnings: list[str] = Field(default_factory=list)


class AnalyzeContractRequest(BaseModel):
    extraction_model_id: int | None = None


class ConfirmRelationshipRequest(BaseModel):
    action: Literal["confirm", "reject"]


class ConfirmRelationshipResponse(BaseModel):
    document_id: str
    status: Literal["confirmed", "rejected"]
    relationship: DetectedRelationship | None = None


class ChildRelationship(BaseModel):
    child_document_id: str
    child_document_title: str
    child_document_number: str | None = None

    relationship_type: str

    confidence: float = Field(ge=0, le=1)

    status: Literal[
        "pending",
        "confirmed",
        "rejected",
    ]


class ChildRelationshipsResponse(BaseModel):
    parent_document_id: str
    children: list[ChildRelationship] = Field(default_factory=list)


class ApproveDocumentRequest(BaseModel):
    changed_by: str = Field(min_length=1, max_length=120)


class ApproveDocumentResponse(BaseModel):
    document_id: str
    approved_by: str
    approved_at: datetime
