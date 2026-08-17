from abc import ABC, abstractmethod
from typing import Any

from app.services.contract_field_schema import FieldSpec


class AIProviderError(Exception):
    """Raised when an AI provider cannot complete a request."""


class AIProvider(ABC):

    @abstractmethod
    async def extract(
        self,
        *,
        instruction: str,
        page_context: str,
    ) -> dict[str, Any]:

        raise NotImplementedError

    @abstractmethod
    async def classify(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:

        raise NotImplementedError

    @abstractmethod
    async def extract_fields(
        self,
        *,
        page_context: str,
        field_specs: list[FieldSpec],
    ) -> dict[str, Any]:

        raise NotImplementedError

    @abstractmethod
    async def extract_clauses(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:

        raise NotImplementedError

    @abstractmethod
    async def extract_signatures(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:

        raise NotImplementedError


class DisabledAIProvider(AIProvider):

    async def extract(
        self,
        *,
        instruction: str,
        page_context: str,
    ) -> dict[str, Any]:

        return {
            "answer": None,
            "values": [],
            "warnings": [
                "AI fallback is disabled."
            ],
        }

    async def classify(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:

        # Graceful degradation: classification without AI can't do
        # better than "unknown", but shouldn't fail the whole pipeline.
        return {
            "document_type": "Other",
            "industry": None,
            "contract_side": "unknown",
            "language": None,
            "confidence": 0.0,
        }

    async def extract_fields(
        self,
        *,
        page_context: str,
        field_specs: list[FieldSpec],
    ) -> dict[str, Any]:

        return {"fields": []}

    async def extract_clauses(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:

        return {"clauses": []}

    async def extract_signatures(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:

        return {"signatures": []}
