from pydantic import BaseModel


class DetectedTable(BaseModel):
    key: str
    label: str
    pages: list[int]
    confidence: float


class DetectedField(BaseModel):
    key: str
    label: str
    pages: list[int]


class ContentStats(BaseModel):
    tables: int
    dates: int
    currency_values: int
    organizations: int


class StructureDetectionResponse(BaseModel):
    document_id: str

    document_family: str
    document_family_label: str

    detected_fields: list[DetectedField]
    detected_tables: list[DetectedTable]
    detected_contacts: list[str]
    detected_obligations: list[str]

    content_stats: ContentStats
