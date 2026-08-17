from app.core.config import get_settings
from app.models.document_page import DocumentPage
from app.schemas.contract_analysis import ContractClassification
from app.services.ai_context import build_page_context
from app.services.ai_provider import AIProvider

CLASSIFICATION_PAGE_LIMIT = 3


async def classify_contract(
    *,
    pages: list[DocumentPage],
    ai_provider: AIProvider,
) -> ContractClassification:
    """
    Contract type/industry/side is almost always evident from the
    opening pages, so only those are sent to keep this cheap.
    """

    settings = get_settings()

    context_pages = pages[:CLASSIFICATION_PAGE_LIMIT]

    context = build_page_context(
        context_pages,
        maximum_characters=settings.ai_max_context_chars,
    )

    result = await ai_provider.classify(
        page_context=context,
    )

    return ContractClassification.model_validate(result)
