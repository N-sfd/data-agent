from typing import Any, Literal

from pydantic import BaseModel, Field


class RateCardRow(BaseModel):
    role: str
    rate: float | None = None
    unit: str | None = None
    currency: str | None = None


class NormalizedTable(BaseModel):
    table_id: str
    table_type: Literal["rate_card", "generic"]

    page_number: int
    source_reference: str

    headers: list[str]
    rows: list[dict[str, Any]]

    rate_card_rows: list[RateCardRow] = Field(default_factory=list)


class TableExtractionResponse(BaseModel):
    document_id: str
    tables: list[NormalizedTable]
