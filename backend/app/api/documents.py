from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.dependencies import get_database
from app.models.document import Document
from app.schemas.document import UploadedDocumentResponse
from app.services.file_upload import (
    UploadValidationError,
    save_pdf_stream,
)
from app.services.pdf_validation import (
    PDFValidationError,
    validate_pdf_structure,
)

router = APIRouter()
settings = get_settings()


@router.post(
    "/upload",
    response_model=UploadedDocumentResponse,
    status_code=201,
)
async def upload_pdf(
    file: UploadFile = File(...),
    database: Session = Depends(get_database),
) -> UploadedDocumentResponse:
    document_id = uuid4()
    stored_filename = f"{document_id}.pdf"
    destination = settings.upload_path / stored_filename
    maximum_size_bytes = settings.max_upload_mb * 1024 * 1024

    try:
        saved_upload = await save_pdf_stream(
            file=file,
            document_id=document_id,
            destination=destination,
            max_size_bytes=maximum_size_bytes,
        )

        pdf_metadata = validate_pdf_structure(
            saved_upload.stored_path,
            max_pages=settings.max_pdf_pages,
            allow_encrypted=settings.allow_encrypted_pdf,
        )

        # Portfolio extraction may replace the stored bytes in place.
        file_bytes = destination.read_bytes()
        size_bytes = len(file_bytes)
        checksum = sha256(file_bytes).hexdigest()

        display_filename = saved_upload.original_filename

        if (
            pdf_metadata.extracted_from_portfolio
            and pdf_metadata.embedded_filename
        ):
            display_filename = (
                f"{saved_upload.original_filename} "
                f"→ {pdf_metadata.embedded_filename}"
            )

        duplicate_statement = select(Document).where(
            Document.checksum_sha256
            == checksum
        )

        duplicate = database.scalar(duplicate_statement)

        if duplicate is not None:
            destination.unlink(missing_ok=True)

            # Idempotent upload: reuse the existing document so the
            # frontend can continue extraction / analysis.
            return UploadedDocumentResponse(
                document_id=duplicate.id,
                original_filename=duplicate.original_filename,
                status=duplicate.status,
                content_type=duplicate.content_type,
                size_bytes=duplicate.size_bytes,
                checksum_sha256=duplicate.checksum_sha256,
                page_count=duplicate.page_count,
                encrypted=duplicate.encrypted,
                uploaded_at=duplicate.uploaded_at,
                message=(
                    "This PDF was already uploaded. "
                    "Continuing with the existing document."
                ),
            )

        uploaded_at = datetime.now(timezone.utc)

        document = Document(
            id=str(document_id),
            original_filename=display_filename,
            stored_filename=stored_filename,
            content_type="application/pdf",
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            page_count=pdf_metadata.page_count,
            encrypted=pdf_metadata.encrypted,
            status="ready",
            uploaded_at=uploaded_at,
        )

        database.add(document)
        database.commit()

        if pdf_metadata.extracted_from_portfolio:
            message = (
                "PDF Portfolio detected. Extracted embedded document "
                f"'{pdf_metadata.embedded_filename}' "
                f"({pdf_metadata.page_count} pages) for analysis."
            )
        else:
            message = (
                "The PDF was uploaded securely. Specify the pages, "
                "financial section, table, account, or reporting period "
                "you want to extract."
            )

        return UploadedDocumentResponse(
            document_id=document_id,
            original_filename=display_filename,
            status="ready",
            content_type="application/pdf",
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            page_count=pdf_metadata.page_count,
            encrypted=pdf_metadata.encrypted,
            uploaded_at=uploaded_at,
            message=message,
        )

    except HTTPException:
        raise

    except UploadValidationError as exc:
        destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except PDFValidationError as exc:
        destination.unlink(missing_ok=True)

        message = str(exc)

        if "PDF Portfolio" in message:
            raise HTTPException(
                status_code=422,
                detail={
                    "status": "unsupported_container",
                    "message": message,
                },
            ) from exc

        raise HTTPException(
            status_code=422,
            detail=message,
        ) from exc

    except Exception as exc:
        destination.unlink(missing_ok=True)
        database.rollback()

        raise HTTPException(
            status_code=500,
            detail="The PDF could not be stored securely.",
        ) from exc
