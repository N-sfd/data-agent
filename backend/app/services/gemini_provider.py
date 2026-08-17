import json
from typing import Any

from google import genai

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
from app.prompts.universal_extraction import (
    UNIVERSAL_EXTRACTION_SYSTEM_PROMPT,
)
from app.schemas.ai_extraction import (
    AIClauseExtractionResult,
    AIExtractionResult,
    AIFieldExtractionResult,
    AISignatureExtractionResult,
)
from app.schemas.contract_analysis import (
    ContractClassification,
)
from app.services.ai_provider import (
    AIProvider,
    AIProviderError,
)
from app.services.contract_field_schema import FieldSpec


class GeminiAIProvider(AIProvider):

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
    ) -> None:

        if not api_key:
            raise AIProviderError(
                "Gemini API key is missing."
            )

        self.client = genai.Client(
            api_key=api_key
        )

        self.model = model

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
            system_instruction=(
                UNIVERSAL_EXTRACTION_SYSTEM_PROMPT
            ),
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
            system_instruction=(
                CLASSIFICATION_SYSTEM_PROMPT
            ),
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
            system_instruction=(
                METADATA_EXTRACTION_SYSTEM_PROMPT
            ),
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
            system_instruction=(
                CLAUSE_EXTRACTION_SYSTEM_PROMPT
            ),
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
            system_instruction=(
                SIGNATURE_EXTRACTION_SYSTEM_PROMPT
            ),
            user_prompt=user_prompt,
            response_schema=AISignatureExtractionResult,
            failure_label="signature extraction",
        )

    async def _generate(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
        response_schema: type,
        failure_label: str,
    ) -> dict[str, Any]:

        try:

            response = self.client.models.generate_content(
                model=self.model,

                contents=user_prompt,

                config={
                    "system_instruction":
                        system_instruction,

                    "response_mime_type":
                        "application/json",

                    "response_schema":
                        response_schema,
                },
            )

            if not response.text:

                raise AIProviderError(
                    "Gemini returned an empty response."
                )

            parsed = json.loads(
                response.text
            )

            validated = (
                response_schema
                .model_validate(
                    parsed
                )
            )

            return (
                validated.model_dump()
            )

        except AIProviderError:
            raise

        except Exception as exc:

            raise AIProviderError(
                f"Gemini {failure_label} failed: {exc}"
            ) from exc
