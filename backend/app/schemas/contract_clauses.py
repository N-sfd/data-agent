from pydantic import BaseModel, Field

from app.schemas.universal_extraction import SourceEvidence


class ClauseResult(BaseModel):
    clause_type: str

    classification: str

    extracted_text: str

    value_summary: str = ""

    confidence: float = Field(ge=0, le=1)

    evidence: SourceEvidence


class ClauseExtractionResponse(BaseModel):
    document_id: str

    clauses: list[ClauseResult]

    warnings: list[str] = Field(default_factory=list)
