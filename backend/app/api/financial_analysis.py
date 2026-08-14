from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.dependencies import (
    get_database,
)
from app.models.document import Document
from app.schemas.financial_analysis import (
    FinancialAnalysisRequest,
    FinancialAnalysisResponse,
)
from app.services.financial_scope import (
    select_relevant_pages,
)
from app.services.financial_table_extractor import (
    extract_tables_from_pages,
)


router = APIRouter()

settings = get_settings()


@router.post(
    "/{document_id}/analyze",
    response_model=FinancialAnalysisResponse,
)
async def analyze_financial_document(
    document_id: str,
    request: FinancialAnalysisRequest,
    database: Session = Depends(
        get_database
    ),
) -> FinancialAnalysisResponse:

    document = database.get(
        Document,
        document_id,
    )

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
                "Run page extraction before "
                "financial analysis."
            ),
        )

    pages_used = select_relevant_pages(
        database=database,
        document_id=document_id,
        instruction=request.instruction,
        page_start=request.page_start,
        page_end=request.page_end,
    )

    if not pages_used:
        raise HTTPException(
            status_code=422,
            detail=(
                "I could not determine which "
                "pages contain the requested "
                "information. Specify a section, "
                "financial category, or page range."
            ),
        )

    file_path = (
        settings.upload_path
        / document.stored_filename
    )

    tables = extract_tables_from_pages(
        file_path=file_path,
        original_filename=(
            document.original_filename
        ),
        page_numbers=pages_used,
    )

    warnings: list[str] = []

    if not tables:
        warnings.append(
            "Relevant pages were found, "
            "but no structured tables were "
            "detected on those pages."
        )

    return FinancialAnalysisResponse(
        document_id=document_id,
        instruction=request.instruction,
        pages_used=pages_used,
        tables=tables,
        status="completed",
        warnings=warnings,
    )