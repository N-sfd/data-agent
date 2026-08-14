from abc import ABC, abstractmethod
from typing import Any


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
