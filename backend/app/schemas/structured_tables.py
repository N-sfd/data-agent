from pydantic import BaseModel, Field

from app.schemas.universal_extraction import SourceEvidence


class LineItemResult(BaseModel):
    clin: str | None = None
    description: str = ""
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount: float | None = None
    is_maximum: bool = False
    period_label: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class PerformancePeriodResult(BaseModel):
    period_label: str = ""
    start_date: str | None = None
    end_date: str | None = None
    amount: float | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class DeliveryScheduleResult(BaseModel):
    clin: str | None = None
    delivery_date: str | None = None
    quantity: float | None = None
    ship_to_address: str | None = None
    dodaac: str | None = None
    cage_code: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class KeyPositionResult(BaseModel):
    position_title: str = ""
    pir: str | None = None
    code: str | None = None
    monthly_amount: float | None = None
    pws_section: str | None = None
    wawf_field: str | None = None
    wawf_value: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class FundingLineResult(BaseModel):
    acrn: str | None = None
    line_of_accounting: str | None = None
    amount: float | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class ClauseReferenceResult(BaseModel):
    clause_family: str
    clause_number: str
    title: str = ""
    effective_date: str | None = None
    alternate: str | None = None
    deviation: str | None = None
    variation_effective_date: str | None = None
    full_text: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class WawfInstructionResult(BaseModel):
    field_name: str = ""
    instruction_value: str = ""
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class InsuranceRequirementResult(BaseModel):
    coverage_type: str = ""
    minimum_amount: float | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class OrderRangeResult(BaseModel):
    naics_code: str | None = None
    minimum_amount: float | None = None
    maximum_amount: float | None = None
    description: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class AmendmentHistoryResult(BaseModel):
    amendment_number: str = ""
    effective_date: str | None = None
    description: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class ContactResult(BaseModel):
    contact_name: str = ""
    role_title: str | None = None
    phone_area_code: str | None = None
    phone_number: str | None = None
    phone_extension: str | None = None
    email: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class AddressResult(BaseModel):
    address_type: str
    organization_name: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: SourceEvidence


class StructuredTablesResponse(BaseModel):
    document_id: str

    line_items: list[LineItemResult] = Field(default_factory=list)
    performance_periods: list[PerformancePeriodResult] = Field(default_factory=list)
    delivery_schedule: list[DeliveryScheduleResult] = Field(default_factory=list)
    key_positions: list[KeyPositionResult] = Field(default_factory=list)
    funding_lines: list[FundingLineResult] = Field(default_factory=list)
    clause_references: list[ClauseReferenceResult] = Field(default_factory=list)
    wawf_instructions: list[WawfInstructionResult] = Field(default_factory=list)
    insurance_requirements: list[InsuranceRequirementResult] = Field(default_factory=list)
    order_ranges: list[OrderRangeResult] = Field(default_factory=list)
    amendment_history: list[AmendmentHistoryResult] = Field(default_factory=list)
    contacts: list[ContactResult] = Field(default_factory=list)
    addresses: list[AddressResult] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
