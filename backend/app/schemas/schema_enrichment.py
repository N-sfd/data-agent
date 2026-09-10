"""Pydantic schema for AI semantic target enrichment."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SchemaTargetEnrichment(BaseModel):
    key: str
    display_name: str | None = None
    group: str | None = None
    value_type: str | None = None
    description: str | None = None


class SchemaEnrichmentResult(BaseModel):
    enrichments: list[SchemaTargetEnrichment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
