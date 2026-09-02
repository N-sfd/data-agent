from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DataTypeLiteral = Literal[
    "text",
    "number",
    "currency",
    "date",
    "boolean",
    "list",
]


class ExtractionFieldCreate(BaseModel):
    field_name: str = Field(min_length=1, max_length=120)
    description: str = ""
    data_type: DataTypeLiteral = "text"


class ExtractionFieldResponse(BaseModel):
    id: int
    model_id: int
    field_name: str
    description: str
    data_type: DataTypeLiteral
    created_at: datetime


class ExtractionModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    document_types: list[str] = Field(default_factory=lambda: ["*"])


class ExtractionModelResponse(BaseModel):
    id: int
    name: str
    description: str
    document_types: list[str]
    created_at: datetime
    fields: list[ExtractionFieldResponse] = Field(
        default_factory=list
    )
