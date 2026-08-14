import json
from typing import Any

from google import genai

from app.prompts.universal_extraction import (
    UNIVERSAL_EXTRACTION_SYSTEM_PROMPT,
)
from app.schemas.ai_extraction import (
    AIExtractionResult,
)
from app.services.ai_provider import (
    AIProvider,
    AIProviderError,
)


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

        try:

            response = self.client.models.generate_content(
                model=self.model,

                contents=user_prompt,

                config={
                    "system_instruction":
                        UNIVERSAL_EXTRACTION_SYSTEM_PROMPT,

                    "response_mime_type":
                        "application/json",

                    "response_schema":
                        AIExtractionResult,
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
                AIExtractionResult
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
                f"Gemini extraction failed: {exc}"
            ) from exc
