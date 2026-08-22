import base64

import fitz
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.dependencies import get_database
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.page_text_block import PageTextBlock
from app.schemas.page_extraction import (
    DocumentExtractionProgress,
    DocumentExtractionRequest,
    DocumentExtractionSummary,
    PageRenderResponse,
    StoredBlockResponse,
    StoredPageResponse,
)
from app.services.document_extraction import (
    DocumentExtractionError,
    process_document_pages,
)

router = APIRouter()
settings = get_settings()

RENDER_ZOOM = 2.0
HIGHLIGHT_SEARCH_LIMIT = 120


@router.post(
    "/{document_id}/extract-pages",
    response_model=DocumentExtractionSummary,
)
async def extract_document_pages(
    document_id: str,
    request: DocumentExtractionRequest,
    database: Session = Depends(get_database),
) -> DocumentExtractionSummary:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if document.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=(
                "The document is not ready for extraction."
            ),
        )

    file_path = (
        settings.upload_path / document.stored_filename
    )

    try:
        # PDF rendering and OCR are CPU-bound and can take a long time for
        # documents with many pages. Running them inline would block the
        # single event loop for the whole duration, starving /health and
        # risking a host restarting the process mid-extraction.
        result = await run_in_threadpool(
            process_document_pages,
            database=database,
            document_record=document,
            file_path=file_path,
            settings=settings,
            run_ocr=request.run_ocr,
            page_start=request.page_start,
            page_end=request.page_end,
            force_reprocess=request.force_reprocess,
        )

        return DocumentExtractionSummary(**result)

    except DocumentExtractionError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/{document_id}/progress",
    response_model=DocumentExtractionProgress,
)
async def get_document_extraction_progress(
    document_id: str,
    database: Session = Depends(get_database),
) -> DocumentExtractionProgress:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    # Pages are committed one at a time inside process_document_pages
    # (which runs in a threadpool), so counting rows here reflects
    # live progress even while that request is still in flight.
    page_current = database.scalar(
        select(func.count())
        .select_from(DocumentPage)
        .where(DocumentPage.document_id == document_id)
    ) or 0

    native_pages = database.scalar(
        select(func.count())
        .select_from(DocumentPage)
        .where(
            DocumentPage.document_id == document_id,
            DocumentPage.requires_ocr.is_(False),
        )
    ) or 0

    ocr_pages = database.scalar(
        select(func.count())
        .select_from(DocumentPage)
        .where(
            DocumentPage.document_id == document_id,
            DocumentPage.requires_ocr.is_(True),
        )
    ) or 0

    ocr_completed_pages = database.scalar(
        select(func.count())
        .select_from(DocumentPage)
        .where(
            DocumentPage.document_id == document_id,
            DocumentPage.ocr_succeeded.is_(True),
        )
    ) or 0

    page_total = document.page_count
    percent = (
        round(page_current / page_total * 100)
        if page_total
        else 0
    )

    return DocumentExtractionProgress(
        document_id=document_id,
        status=document.processing_status,
        page_current=page_current,
        page_total=page_total,
        percent=min(percent, 100),
        native_pages=native_pages,
        ocr_pages=ocr_pages,
        ocr_completed_pages=ocr_completed_pages,
    )


@router.get(
    "/{document_id}/pages",
    response_model=list[StoredPageResponse],
)
async def list_document_pages(
    document_id: str,
    database: Session = Depends(get_database),
) -> list[StoredPageResponse]:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    pages = list(
        database.scalars(
            select(DocumentPage)
            .where(
                DocumentPage.document_id == document_id
            )
            .order_by(DocumentPage.page_number)
        )
    )

    return [
        StoredPageResponse(
            document_id=document_id,
            page_number=page.page_number,
            page_label=page.page_label,
            extraction_method=page.extraction_method,
            final_text=page.final_text,
            requires_ocr=page.requires_ocr,
            ocr_attempted=page.ocr_attempted,
            ocr_succeeded=page.ocr_succeeded,
            character_count=page.character_count,
            word_count=page.word_count,
            page_width=page.page_width,
            page_height=page.page_height,
            source_reference=(
                f"{document.original_filename}, "
                f"page {page.page_number}"
            ),
        )
        for page in pages
    ]


@router.get(
    "/{document_id}/pages/{page_number}",
    response_model=StoredPageResponse,
)
async def get_document_page(
    document_id: str,
    page_number: int,
    database: Session = Depends(get_database),
) -> StoredPageResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    page = database.scalar(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page_number,
        )
    )

    if page is None:
        raise HTTPException(
            status_code=404,
            detail="Extracted page not found.",
        )

    return StoredPageResponse(
        document_id=document_id,
        page_number=page.page_number,
        page_label=page.page_label,
        extraction_method=page.extraction_method,
        final_text=page.final_text,
        requires_ocr=page.requires_ocr,
        ocr_attempted=page.ocr_attempted,
        ocr_succeeded=page.ocr_succeeded,
        character_count=page.character_count,
        word_count=page.word_count,
        page_width=page.page_width,
        page_height=page.page_height,
        source_reference=(
            f"{document.original_filename}, "
            f"page {page.page_number}"
        ),
    )


@router.get(
    "/{document_id}/pages/{page_number}/blocks",
    response_model=list[StoredBlockResponse],
)
async def get_page_blocks(
    document_id: str,
    page_number: int,
    database: Session = Depends(get_database),
) -> list[StoredBlockResponse]:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    page = database.scalar(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page_number,
        )
    )

    if page is None:
        raise HTTPException(
            status_code=404,
            detail="Extracted page not found.",
        )

    blocks = list(
        database.scalars(
            select(PageTextBlock)
            .where(
                PageTextBlock.document_page_id == page.id
            )
            .order_by(PageTextBlock.block_index)
        )
    )

    return [
        StoredBlockResponse(
            block_index=block.block_index,
            block_type=block.block_type,
            text=block.text,
            x0=block.x0,
            y0=block.y0,
            x1=block.x1,
            y1=block.y1,
            extraction_method=block.extraction_method,
            source_reference=(
                f"{document.original_filename}, "
                f"page {page_number}, "
                f"block {block.block_index}"
            ),
        )
        for block in blocks
    ]


@router.get(
    "/{document_id}/pages/{page_number}/render",
    response_model=PageRenderResponse,
)
async def render_document_page(
    document_id: str,
    page_number: int,
    highlight: str | None = None,
    database: Session = Depends(get_database),
) -> PageRenderResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    file_path = settings.upload_path / document.stored_filename

    if (
        not file_path.exists()
        or file_path.suffix.lower() != ".pdf"
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Page rendering is only available for PDF documents."
            ),
        )

    pdf: fitz.Document | None = None

    try:
        pdf = fitz.open(file_path)

        if page_number < 1 or page_number > pdf.page_count:
            raise HTTPException(
                status_code=404,
                detail="Page not found.",
            )

        page = pdf.load_page(page_number - 1)

        matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
        pixmap = page.get_pixmap(matrix=matrix)
        image_bytes = pixmap.tobytes("png")

        image_data_url = (
            "data:image/png;base64,"
            + base64.b64encode(image_bytes).decode("ascii")
        )

        highlight_box = None

        if highlight:
            rects = page.search_for(
                highlight[:HIGHLIGHT_SEARCH_LIMIT]
            )

            if rects:
                rect = rects[0]
                highlight_box = {
                    "x0": rect.x0,
                    "y0": rect.y0,
                    "x1": rect.x1,
                    "y1": rect.y1,
                }

        return PageRenderResponse(
            page_number=page_number,
            image_data_url=image_data_url,
            page_width=page.rect.width,
            page_height=page.rect.height,
            highlight=highlight_box,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="The page could not be rendered.",
        ) from exc

    finally:
        if pdf is not None:
            pdf.close()
