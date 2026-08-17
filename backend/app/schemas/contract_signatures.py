from pydantic import BaseModel, Field

from app.schemas.universal_extraction import SourceEvidence


class SignatureResult(BaseModel):
    party_name: str

    signatory_name: str = ""

    signatory_title: str = ""

    signed: bool = False

    signature_date: str | None = None

    confidence: float = Field(ge=0, le=1)

    evidence: SourceEvidence


class SignatureExtractionResponse(BaseModel):
    document_id: str

    signatures: list[SignatureResult]

    warnings: list[str] = Field(default_factory=list)
