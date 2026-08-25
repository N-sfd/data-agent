from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import STRUCTURE_DETECTION_FAILED, TARGET_NOT_FOUND, http_error
from app.database.dependencies import (
    get_database,
)
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.document_target import (
    DiscoverSchemaResponse,
    ExtractTargetsRequest,
    ExtractTargetsResponse,
)
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
from app.services.detected_target_store import (
    load_document_targets,
    persist_document_targets,
)
from app.services.schema_discovery import discover_document_schema
from app.services.structure_detection import (
    detect_document_structures,
)
from app.services.target_extraction_service import extract_by_targets
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


def _load_document_or_404(database: Session, document_id: str) -> Document:
    document = database.get(Document, document_id)
    if document is None:
        raise http_error(404, TARGET_NOT_FOUND, "Document not found.")
    return document


@router.post(
    "/{document_id}/discover-schema",
    response_model=DiscoverSchemaResponse,
)
async def discover_schema(
    document_id: str,
    database: Session = Depends(get_database),
) -> DiscoverSchemaResponse:

    document = _load_document_or_404(database, document_id)

    if document.processing_status not in {
        "completed",
        "completed_with_warnings",
    }:
        raise http_error(
            409,
            STRUCTURE_DETECTION_FAILED,
            "Run page extraction before schema discovery.",
        )

    pages = list(
        database.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
    )

    ai_provider = create_ai_provider(settings)

    try:
        result = await discover_document_schema(
            document=document,
            pages=pages,
            ai_provider=ai_provider,
        )
    except Exception as exc:
        raise http_error(
            500,
            STRUCTURE_DETECTION_FAILED,
            "Schema discovery failed.",
        ) from exc

    persist_document_targets(database=database, result=result)

    return result


@router.get(
    "/{document_id}/targets",
    response_model=DiscoverSchemaResponse,
)
async def get_targets(
    document_id: str,
    database: Session = Depends(get_database),
) -> DiscoverSchemaResponse:

    _load_document_or_404(database, document_id)

    result = load_document_targets(database=database, document_id=document_id)

    if result is None:
        raise http_error(
            404,
            TARGET_NOT_FOUND,
            "No discovered targets yet. Call discover-schema first.",
        )

    return result


@router.post(
    "/{document_id}/extract-targets",
    response_model=ExtractTargetsResponse,
)
async def extract_targets(
    document_id: str,
    request: ExtractTargetsRequest,
    database: Session = Depends(get_database),
) -> ExtractTargetsResponse:

    document = _load_document_or_404(database, document_id)

    ai_provider = create_ai_provider(settings)

    return await extract_by_targets(
        database=database,
        document=document,
        target_ids=request.target_ids,
        use_ai_fallback=(
            request.use_ai_fallback and settings.ai_fallback_enabled
        ),
        ai_provider=ai_provider,
    )
