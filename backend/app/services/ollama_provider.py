import json
import logging
from typing import Any

import httpx

from app.prompts.classification import (
    CLASSIFICATION_SYSTEM_PROMPT,
)
from app.prompts.clause_extraction import (
    CLAUSE_EXTRACTION_SYSTEM_PROMPT,
)
from app.prompts.metadata_extraction import (
    METADATA_EXTRACTION_SYSTEM_PROMPT,
    build_field_request_block,
)
from app.prompts.signature_extraction import (
    SIGNATURE_EXTRACTION_SYSTEM_PROMPT,
)
from app.prompts.structured_table_extraction import (
    STRUCTURED_TABLE_EXTRACTION_SYSTEM_PROMPT,
    build_structured_table_request_block,
)
from app.prompts.schema_enrichment import SCHEMA_ENRICHMENT_SYSTEM_PROMPT
from app.prompts.universal_extraction import (
    UNIVERSAL_EXTRACTION_SYSTEM_PROMPT,
)
from app.schemas.ai_extraction import (
    AIClauseExtractionResult,
    AIExtractionResult,
    AIFieldExtractionResult,
    AISignatureExtractionResult,
    AIStructuredTablesResult,
)
from app.schemas.contract_analysis import (
    ContractClassification,
)
from app.schemas.schema_enrichment import SchemaEnrichmentResult
from app.services.ai_provider import (
    AIProvider,
    AIProviderError,
)
from app.services.contract_field_schema import FieldSpec
from app.services.contract_structured_table_schema import StructuredTableSpec

logger = logging.getLogger(__name__)


class OllamaAIProvider(AIProvider):
    """
    Local AI fallback provider using Ollama's REST API.
    Provides structured JSON extraction without external cloud dependency.
    """

    provider_id = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.model = model or "llama3.2"
        self.timeout_seconds = timeout_seconds

    async def extract(
        self,
        *,
        instruction: str,
        page_context: str,
    ) -> dict[str, Any]:
        user_prompt = f"""USER REQUEST:

{instruction}


DOCUMENT CONTENT:

{page_context}
"""
        return await self._generate(
            system_instruction=UNIVERSAL_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=AIExtractionResult,
            failure_label="extraction",
        )

    async def classify(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:
        user_prompt = f"""DOCUMENT CONTENT:

{page_context}
"""
        return await self._generate(
            system_instruction=CLASSIFICATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=ContractClassification,
            failure_label="classification",
        )

    async def extract_fields(
        self,
        *,
        page_context: str,
        field_specs: list[FieldSpec],
    ) -> dict[str, Any]:
        field_block = build_field_request_block(field_specs)
        user_prompt = f"""{field_block}


DOCUMENT CONTENT:

{page_context}
"""
        return await self._generate(
            system_instruction=METADATA_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=AIFieldExtractionResult,
            failure_label="field extraction",
        )

    async def extract_clauses(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:
        user_prompt = f"""DOCUMENT CONTENT:

{page_context}
"""
        return await self._generate(
            system_instruction=CLAUSE_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=AIClauseExtractionResult,
            failure_label="clause extraction",
        )

    async def extract_signatures(
        self,
        *,
        page_context: str,
    ) -> dict[str, Any]:
        user_prompt = f"""DOCUMENT CONTENT:

{page_context}
"""
        return await self._generate(
            system_instruction=SIGNATURE_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=AISignatureExtractionResult,
            failure_label="signature extraction",
        )

    async def extract_structured_tables(
        self,
        *,
        page_context: str,
        table_specs: list[StructuredTableSpec],
    ) -> dict[str, Any]:
        table_block = build_structured_table_request_block(table_specs)
        user_prompt = f"""{table_block}


DOCUMENT CONTENT:

{page_context}
"""
        return await self._generate(
            system_instruction=STRUCTURED_TABLE_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=AIStructuredTablesResult,
            failure_label="structured table extraction",
        )

    async def enrich_schema(
        self,
        *,
        targets_json: str,
        page_context: str,
    ) -> dict[str, Any]:
        user_prompt = f"""DISCOVERED TARGETS (JSON):

{targets_json}


DOCUMENT CONTENT (evidence sample):

{page_context}
"""
        return await self._generate(
            system_instruction=SCHEMA_ENRICHMENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=SchemaEnrichmentResult,
            failure_label="schema enrichment",
        )

    async def _generate(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
        response_schema: type,
        failure_label: str,
    ) -> dict[str, Any]:
        endpoint = f"{self.base_url}/api/generate"
        combined_prompt = f"{system_instruction}\n\nRespond with valid JSON matching the schema.\n\n{user_prompt}"

        payload = {
            "model": self.model,
            "prompt": combined_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(endpoint, json=payload)

            if response.status_code != 200:
                raise AIProviderError(
                    f"Ollama returned HTTP {response.status_code}: {response.text[:200]}"
                )

            data = response.json()
            raw_response = data.get("response", "")

            if not raw_response or not raw_response.strip():
                raise AIProviderError("Ollama returned an empty response.")

            parsed = json.loads(raw_response)
            validated = response_schema.model_validate(parsed)
            return validated.model_dump()

        except AIProviderError:
            raise
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                f"Ollama response for {failure_label} was not valid JSON: {exc}"
            ) from exc
        except Exception as exc:
            raise AIProviderError(
                f"Ollama {failure_label} failed: {exc}"
            ) from exc
