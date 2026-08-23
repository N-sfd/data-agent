from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.dependencies import (
    get_database,
)
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.structure_detection import (
    StructureDetectionResponse,
)
from app.schemas.universal_extraction import (
    UniversalExtractionRequest,
    UniversalExtractionResponse,
)
from app.services.ai_provider_factory import (
    create_ai_provider,
)
from app.services.structure_detection import (
    detect_document_structures,
)
from app.services.universal_extraction_service import (
    universal_extract,
)


router = APIRouter()
settings = get_settings()


@router.post(
    "/{document_id}/extract",
    response_model=(
        UniversalExtractionResponse
    ),
)
async def extract_anything(
    document_id: str,
    request: UniversalExtractionRequest,
    database: Session = Depends(
        get_database
    ),
) -> UniversalExtractionResponse:

    document = database.get(
        Document,
        document_id,
    )

    if document is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if (
        document.processing_status
        not in {
            "completed",
            "completed_with_warnings",
        }
    ):

        raise HTTPException(
            status_code=409,
            detail=(
                "Run page extraction "
                "before universal extraction."
            ),
        )

    ai_provider = create_ai_provider(
        settings
    )

    return await universal_extract(
        database=database,
        document=document,
        instruction=request.instruction,
        max_pages=min(
            request.max_pages,
            settings.ai_max_pages,
        ),
        use_ai_fallback=(
            request.use_ai_fallback
            and settings.ai_fallback_enabled
        ),
        ai_provider=ai_provider,
    )


@router.post(
    "/{document_id}/detect-structures",
    response_model=StructureDetectionResponse,
)
async def detect_structures(
    document_id: str,
    database: Session = Depends(get_database),
) -> StructureDetectionResponse:

    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if document.processing_status not in {
        "completed",
        "completed_with_warnings",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Run page extraction "
                "before detecting document structures."
            ),
        )

    pages = list(
        database.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
    )

    ai_provider = create_ai_provider(settings)

    return await detect_document_structures(
        document=document,
        pages=pages,
        ai_provider=ai_provider,
    )
