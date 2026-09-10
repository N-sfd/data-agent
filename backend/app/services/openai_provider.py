"""OpenAI Chat Completions provider implementing the shared AIProvider surface."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.prompts.classification import CLASSIFICATION_SYSTEM_PROMPT
from app.prompts.clause_extraction import CLAUSE_EXTRACTION_SYSTEM_PROMPT
from app.prompts.metadata_extraction import (
    METADATA_EXTRACTION_SYSTEM_PROMPT,
    build_field_request_block,
)
from app.prompts.schema_enrichment import SCHEMA_ENRICHMENT_SYSTEM_PROMPT
from app.prompts.signature_extraction import SIGNATURE_EXTRACTION_SYSTEM_PROMPT
from app.prompts.structured_table_extraction import (
    STRUCTURED_TABLE_EXTRACTION_SYSTEM_PROMPT,
    build_structured_table_request_block,
)
from app.prompts.universal_extraction import UNIVERSAL_EXTRACTION_SYSTEM_PROMPT
from app.schemas.ai_extraction import (
    AIClauseExtractionResult,
    AIExtractionResult,
    AIFieldExtractionResult,
    AISignatureExtractionResult,
    AIStructuredTablesResult,
)
from app.schemas.contract_analysis import ContractClassification
from app.schemas.schema_enrichment import SchemaEnrichmentResult
from app.services.ai_provider import AIProvider, AIProviderError
from app.services.contract_field_schema import FieldSpec
from app.services.contract_structured_table_schema import StructuredTableSpec


class OpenAIAIProvider(AIProvider):
    provider_id = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 90.0,
    ) -> None:
        if not api_key:
            raise AIProviderError("OpenAI API key is missing.")
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"
        self.base_url = base_url.rstrip("/")
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
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{system_instruction}\n\n"
                        "Respond with valid JSON matching the requested schema."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    endpoint, headers=headers, json=payload
                )

            if response.status_code != 200:
                raise AIProviderError(
                    f"OpenAI returned HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                )

            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise AIProviderError("OpenAI returned no choices.")
            content = (choices[0].get("message") or {}).get("content") or ""
            if not str(content).strip():
                raise AIProviderError("OpenAI returned an empty response.")

            parsed = json.loads(content)
            validated = response_schema.model_validate(parsed)
            return validated.model_dump()

        except AIProviderError:
            raise
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                f"OpenAI response for {failure_label} was not valid JSON: {exc}"
            ) from exc
        except Exception as exc:
            raise AIProviderError(
                f"OpenAI {failure_label} failed: {exc}"
            ) from exc
