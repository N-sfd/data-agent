import json
import re
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
from app.services.ai_provider import (
    AIProvider,
    AIProviderError,
)
from app.services.contract_field_schema import FieldSpec
from app.services.contract_structured_table_schema import StructuredTableSpec


_JSON_FENCE_PATTERN = re.compile(
    r"```(?:json)?\s*(.*?)\s*```",
    re.DOTALL | re.IGNORECASE,
)


def _parse_json_response(
    text: str,
    response_schema: type,
) -> dict[str, Any]:
    cleaned = text.strip()

    fenced = _JSON_FENCE_PATTERN.search(cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()

    parsed = json.loads(cleaned)
    validated = response_schema.model_validate(parsed)
    return validated.model_dump()


class ConveraAIProvider(AIProvider):

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
    ) -> None:
        if not api_key:
            raise AIProviderError(
                "Convera API key is missing."
            )

        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    async def extract(
        self,
        *,
        instruction: str,
        page_context: str,
    ) -> dict[str, Any]:
        user_prompt = f"""
USER REQUEST:

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
        user_prompt = f"""
DOCUMENT CONTENT:

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

        user_prompt = f"""
{field_block}


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
        user_prompt = f"""
DOCUMENT CONTENT:

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
        user_prompt = f"""
DOCUMENT CONTENT:

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

        user_prompt = f"""
{table_block}


DOCUMENT CONTENT:

{page_context}
"""

        return await self._generate(
            system_instruction=STRUCTURED_TABLE_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=AIStructuredTablesResult,
            failure_label="structured table extraction",
        )

    async def _generate(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
        response_schema: type,
        failure_label: str,
    ) -> dict[str, Any]:
        schema_json = json.dumps(
            response_schema.model_json_schema(),
            indent=2,
        )

        system_prompt = (
            f"{system_instruction}\n\n"
            "Respond with valid JSON only. "
            "Do not include markdown fences or commentary.\n\n"
            f"JSON schema:\n{schema_json}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self.api_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "default",
                        "messages": messages,
                    },
                )

            if response.status_code >= 400:
                detail = response.text
                try:
                    detail = response.json().get("detail", detail)
                except Exception:
                    pass
                raise AIProviderError(
                    f"Convera chat failed ({response.status_code}): {detail}"
                )

            payload = response.json()
            content = (payload.get("content") or "").strip()

            if not content:
                raise AIProviderError(
                    "Convera returned an empty response."
                )

            return _parse_json_response(
                content,
                response_schema,
            )

        except AIProviderError:
            raise

        except Exception as exc:
            raise AIProviderError(
                f"Convera {failure_label} failed: {exc}"
            ) from exc
