from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import fitz
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.dependencies import get_database
from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.models.document_page import DocumentPage
from app.models.metadata_field_audit_log import MetadataFieldAuditLog
from app.schemas.contract_analysis import (
    GlobalAuditEntry,
    GlobalAuditLogResponse,
)
from app.schemas.document import (
    DocumentHierarchyResponse,
    DocumentSearchResponse,
    DocumentSummaryResponse,
    EmbeddedFileSummary,
    ExistingDocumentSummary,
    HierarchyNode,
    ResolveDuplicateRequest,
    SelectPortfolioFileRequest,
    UploadedDocumentResponse,
)
from app.services.dashboard_stats import (
    compute_document_confidence,
    compute_document_status,
)
from app.core.auth import ActorContext, require_permission
from app.core.observability import bind_job_context, log_event
from app.services.document_storage import (
    DocumentStorageError,
    delete_object,
    ensure_local_copy,
    is_file_available,
    source_status_for,
    upload_object,
)
from app.services.file_upload import (
    UploadValidationError,
    sanitize_display_filename,
    save_upload_stream,
    validate_upload_metadata,
)
from app.services.pdf_validation import (
    EmbeddedPdf,
    PDFMetadata,
    PDFValidationError,
    detect_pdf_portfolio,
    extract_named_embedded_pdf,
    list_embedded_pdfs,
    validate_pdf_structure,
)
from app.services.native_ingest import ingest_native_document
from app.services.upload_processing import (
    assert_legacy_office_supported,
    enqueue_processing_job,
    seed_upload_provenance,
    upload_processing_plan,
)
from app.services.security_validation import (
    NATIVE_PAGE_KINDS,
    SecurityValidationError,
    UPLOAD_TYPES,
    UploadTypeSpec,
    validate_docx_structure,
    validate_pptx_structure,
    validate_xlsx_structure,
)

router = APIRouter()
settings = get_settings()


def _existing_document_summary(
    document: Document,
) -> ExistingDocumentSummary:
    return ExistingDocumentSummary(
        document_id=document.id,
        original_filename=document.original_filename,
        size_bytes=document.size_bytes,
        uploaded_at=document.uploaded_at,
        file_available=is_file_available(
            settings, stored_filename=document.stored_filename
        ),
    )


def _find_duplicate(
    database: Session, checksum: str
) -> Document | None:
    statement = select(Document).where(
        Document.checksum_sha256 == checksum
    )

    return database.scalar(statement)


def _find_staged_upload(
    document_id: UUID,
) -> tuple[Path, UploadTypeSpec] | None:
    for extension, spec in UPLOAD_TYPES.items():
        candidate = settings.upload_path / f"{document_id}{extension}"

        if candidate.exists():
            return candidate, spec

        # Multi-instance / ephemeral disk: restore staged bytes from remote.
        try:
            ensure_local_copy(
                settings, stored_filename=f"{document_id}{extension}"
            )
        except DocumentStorageError:
            continue

        if candidate.exists():
            return candidate, spec

    return None


def _peek_portfolio_embedded_files(file_path: Path) -> list[EmbeddedPdf]:
    try:
        with fitz.open(file_path) as pdf:
            if not pdf.is_pdf or not detect_pdf_portfolio(pdf):
                return []
            return list_embedded_pdfs(pdf)
    except Exception:
        return []


def _extract_metadata(
    spec: UploadTypeSpec, file_path: Path
) -> PDFMetadata:
    if spec.kind == "pdf":
        return validate_pdf_structure(
            file_path,
            max_pages=settings.max_pdf_pages,
            allow_encrypted=settings.allow_encrypted_pdf,
        )

    if spec.kind == "docx":
        validate_docx_structure(file_path)
        return PDFMetadata(
            page_count=1,
            encrypted=False,
            title=None,
            author=None,
        )

    if spec.kind == "xlsx":
        validate_xlsx_structure(file_path)
        from app.parsers.office_text_parsers import parse_xlsx_sheets

        sheet_count = max(len(parse_xlsx_sheets(file_path)), 1)
        return PDFMetadata(
            page_count=sheet_count,
            encrypted=False,
            title=None,
            author=None,
        )

    if spec.kind == "pptx":
        validate_pptx_structure(file_path)
        from app.parsers.office_text_parsers import parse_pptx_slides

        slide_count = max(len(parse_pptx_slides(file_path)), 1)
        return PDFMetadata(
            page_count=slide_count,
            encrypted=False,
            title=None,
            author=None,
        )

    if spec.kind in {"text", "csv", "html", "rtf"}:
        return PDFMetadata(
            page_count=1,
            encrypted=False,
            title=None,
            author=None,
        )

    if spec.kind == "legacy_office":
        # Page count resolved after LibreOffice conversion during extract.
        return PDFMetadata(
            page_count=1,
            encrypted=False,
            title=None,
            author=None,
        )

    # Raster images (png/jpg/tiff/bmp/webp): single page via OCR path.
    return PDFMetadata(
        page_count=1,
        encrypted=False,
        title=None,
        author=None,
    )


def _create_document_record(
    *,
    database: Session,
    document_id: UUID,
    stored_filename: str,
    display_filename: str,
    content_type: str,
    size_bytes: int,
    checksum: str,
    metadata: PDFMetadata,
) -> tuple[Document, datetime]:
    uploaded_at = datetime.now(timezone.utc)

    document = Document(
        id=str(document_id),
        original_filename=display_filename,
        stored_filename=stored_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        checksum_sha256=checksum,
        page_count=metadata.page_count,
        encrypted=metadata.encrypted,
        status="ready",
        uploaded_at=uploaded_at,
    )

    database.add(document)
    database.commit()

    return document, uploaded_at


def _ingest_native_pages(
    database: Session,
    document_id: UUID,
    file_path: Path,
    spec: UploadTypeSpec,
) -> int:
    """Native text/table ingest into the common DocumentPage model."""

    page_count = ingest_native_document(
        database, document_id, file_path, spec
    )

    document = database.get(Document, str(document_id))
    if document is not None:
        document.processing_status = "completed"
        document.processed_page_count = page_count
        document.page_count = page_count

    database.commit()
    return page_count


@router.post(
    "/upload",
    response_model=UploadedDocumentResponse,
    status_code=201,
)
async def upload_document(
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    allow_duplicate: bool = Query(
        False,
        description=(
            "When true, skip duplicate detection and always create a new "
            "document (used after Upload Anyway when the staged file expired)."
        ),
    ),
    database: Session = Depends(get_database),
) -> UploadedDocumentResponse:
    document_id = uuid4()
    destination: Path | None = None
    log: list[str] = []

    try:
        display_filename, spec = validate_upload_metadata(file)
        assert_legacy_office_supported(spec)
        log.append("Validated file type and extension")

        stored_filename = f"{document_id}{spec.extension}"
        destination = settings.upload_path / stored_filename
        maximum_size_bytes = settings.max_upload_mb * 1024 * 1024
        log.append("Generated document ID")

        saved = await save_upload_stream(
            file=file,
            spec=spec,
            document_id=document_id,
            destination=destination,
            max_size_bytes=maximum_size_bytes,
        )
        log.append(
            "Ran security validation "
            "(signature, extension, and MIME checks)"
        )

        if spec.kind == "pdf":
            portfolio_files = _peek_portfolio_embedded_files(destination)

            if len(portfolio_files) > 1:
                log.append(
                    f"Detected a PDF Portfolio with "
                    f"{len(portfolio_files)} embedded documents"
                )

                response.status_code = 200

                return UploadedDocumentResponse(
                    document_id=document_id,
                    original_filename=display_filename,
                    status="portfolio_pending",
                    content_type=spec.content_type,
                    size_bytes=saved.size_bytes,
                    checksum_sha256=None,
                    page_count=1,
                    encrypted=False,
                    uploaded_at=datetime.now(timezone.utc),
                    message=(
                        f"This PDF contains {len(portfolio_files)} "
                        "embedded documents. Choose one to analyze."
                    ),
                    embedded_files=[
                        EmbeddedFileSummary(
                            filename=item.filename,
                            size_bytes=len(item.data),
                        )
                        for item in portfolio_files
                    ],
                    pipeline_log=log,
                )

        metadata = _extract_metadata(spec, destination)

        # Prefer streaming checksum/size from save_upload_stream so medium+
        # files are never fully buffered in RAM for fingerprinting.
        size_bytes = saved.size_bytes
        checksum = saved.checksum_sha256
        log.append("Calculated SHA-256 fingerprint")

        if (
            metadata.extracted_from_portfolio
            and metadata.embedded_filename
        ):
            display_filename = (
                f"{display_filename} → {metadata.embedded_filename}"
            )

        duplicate = None if allow_duplicate else _find_duplicate(database, checksum)

        if duplicate is not None:
            log.append("Checked for duplicates — possible duplicate found")

            # Persist staged bytes remotely so resolve-duplicate works across
            # multi-instance / ephemeral disks (e.g. Render).
            try:
                upload_object(
                    settings,
                    stored_filename,
                    content_type=spec.content_type,
                    file_path=destination,
                    size_bytes=size_bytes,
                )
                log.append("Staged duplicate file to remote storage")
            except DocumentStorageError:
                log.append(
                    "Could not stage duplicate to remote storage — "
                    "resolve may require re-upload"
                )

            # Keep the staged file on disk rather than silently reusing
            # the existing document. The caller decides whether to reuse
            # it or upload anyway via POST /{document_id}/resolve-duplicate.
            response.status_code = 200

            return UploadedDocumentResponse(
                document_id=document_id,
                original_filename=display_filename,
                status="duplicate_pending",
                content_type=spec.content_type,
                size_bytes=size_bytes,
                checksum_sha256=checksum,
                page_count=metadata.page_count,
                encrypted=metadata.encrypted,
                uploaded_at=datetime.now(timezone.utc),
                message=(
                    "A document with identical contents was already "
                    "uploaded. Choose whether to use the existing "
                    "document or upload this one anyway."
                ),
                duplicate=True,
                existing_document=_existing_document_summary(
                    duplicate
                ),
                pipeline_log=log,
            )

        if allow_duplicate:
            log.append("Duplicate check skipped (allow_duplicate=true)")
        else:
            log.append("Checked for duplicates — none found")
        log.append(f"Extracted {spec.kind.upper()} metadata")

        document, uploaded_at = _create_document_record(
            database=database,
            document_id=document_id,
            stored_filename=stored_filename,
            display_filename=display_filename,
            content_type=spec.content_type,
            size_bytes=size_bytes,
            checksum=checksum,
            metadata=metadata,
        )
        bind_job_context(document_id=str(document_id))
        upload_object(
            settings,
            stored_filename,
            content_type=spec.content_type,
            file_path=destination,
            size_bytes=size_bytes,
        )
        log.append("Stored original document")

        size_tier, prefer_background = upload_processing_plan(size_bytes)
        provenance = seed_upload_provenance(
            document,
            spec=spec,
            size_bytes=size_bytes,
            processing_mode="background" if prefer_background else "sync",
        )
        database.commit()

        processing_job_id: int | None = None

        if prefer_background:
            processing_job_id = enqueue_processing_job(
                database=database,
                background_tasks=background_tasks,
                document_id=str(document_id),
            )
            provenance = seed_upload_provenance(
                document,
                spec=spec,
                size_bytes=size_bytes,
                processing_mode="background",
                processing_job_id=processing_job_id,
            )
            database.commit()
            log.append(
                f"Queued background processing job #{processing_job_id} "
                f"({size_tier} upload)"
            )
            message = (
                "Document uploaded and queued for background processing. "
                "Large files are processed asynchronously."
            )
        else:
            if spec.kind in NATIVE_PAGE_KINDS:
                # DOCX/PPTX may OCR embedded scanned images synchronously
                # inside this call — keep it off the event loop so one
                # slow/hung Tesseract call can't stall the whole API.
                page_count = await run_in_threadpool(
                    _ingest_native_pages,
                    database,
                    document_id,
                    destination,
                    spec,
                )
                metadata = PDFMetadata(
                    page_count=page_count,
                    encrypted=False,
                    title=None,
                    author=None,
                )
                provenance = seed_upload_provenance(
                    document,
                    spec=spec,
                    size_bytes=size_bytes,
                    processing_mode="sync",
                )
                provenance["page_count"] = page_count
                document.ingestion_provenance = provenance
                database.commit()
                log.append("Extracted document text")

            if metadata.extracted_from_portfolio:
                message = (
                    "PDF Portfolio detected. Extracted embedded document "
                    f"'{metadata.embedded_filename}' "
                    f"({metadata.page_count} pages) for analysis."
                )
            elif spec.kind in NATIVE_PAGE_KINDS:
                message = (
                    "The document was uploaded and its text extracted. "
                    "Specify what you want to extract or ask a question."
                )
            elif spec.kind == "image":
                message = (
                    "The image was uploaded securely. Extract pages to run "
                    "OCR before asking questions about it."
                )
            elif spec.kind == "legacy_office":
                message = (
                    "Legacy Office file uploaded. Extract pages to convert "
                    "via LibreOffice and run the intelligence pipeline."
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
            content_type=spec.content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            page_count=metadata.page_count,
            encrypted=metadata.encrypted,
            uploaded_at=uploaded_at,
            message=message,
            pipeline_log=log,
            size_tier=size_tier,
            prefer_background=prefer_background,
            processing_job_id=processing_job_id,
            ingestion_provenance=document.ingestion_provenance,
        )

    except HTTPException:
        raise

    except UploadValidationError as exc:
        if destination is not None:
            destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except SecurityValidationError as exc:
        if destination is not None:
            destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except PDFValidationError as exc:
        if destination is not None:
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

    except DocumentStorageError as exc:
        size_for_log = None
        if destination is not None and destination.exists():
            size_for_log = destination.stat().st_size
            destination.unlink(missing_ok=True)

        database.rollback()
        log_event(
            "document_storage_failed",
            stage="upload",
            status="error",
            error_category=exc.error_type,
            document_id=str(document_id),
            size_bytes=size_for_log,
            content_type=getattr(file, "content_type", None),
            storage_provider="supabase",
            error_type=exc.error_type,
            http_status=exc.http_status,
        )

        raise HTTPException(
            status_code=500,
            detail="The file could not be stored securely.",
        ) from exc

    except Exception as exc:
        size_for_log = None
        if destination is not None and destination.exists():
            size_for_log = destination.stat().st_size
            destination.unlink(missing_ok=True)

        database.rollback()
        log_event(
            "document_storage_failed",
            stage="upload",
            status="error",
            error_category=type(exc).__name__,
            document_id=str(document_id),
            size_bytes=size_for_log,
            content_type=getattr(file, "content_type", None),
            storage_provider="supabase",
            error_type=type(exc).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="The file could not be stored securely.",
        ) from exc


@router.post(
    "/{document_id}/resolve-duplicate",
    response_model=UploadedDocumentResponse,
)
async def resolve_duplicate(
    document_id: UUID,
    payload: ResolveDuplicateRequest,
    database: Session = Depends(get_database),
) -> UploadedDocumentResponse:
    staged = _find_staged_upload(document_id)

    if staged is None:
        # Staged file expired (ephemeral disk / multi-instance). Still allow
        # opening the existing document; for upload_anyway the client must
        # re-POST with allow_duplicate=true.
        if payload.action == "use_existing":
            existing_id = payload.existing_document_id
            if existing_id is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "No pending upload found for this document id, "
                        "and no existing_document_id was provided."
                    ),
                )
            duplicate = database.get(Document, str(existing_id))
            if duplicate is None:
                raise HTTPException(
                    status_code=404,
                    detail="Existing document not found.",
                )
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
                message="Continuing with the existing document.",
                pipeline_log=["Reused the existing document"],
                approved_by=duplicate.approved_by,
                approved_at=duplicate.approved_at,
                source_status=source_status_for(
                    settings, stored_filename=duplicate.stored_filename
                ),
                reused_existing=True,
            )

        raise HTTPException(
            status_code=409,
            detail=(
                "STAGED_UPLOAD_EXPIRED: The temporary upload is no longer "
                "on the server. Re-upload with allow_duplicate=true."
            ),
        )

    destination, spec = staged
    size_bytes = destination.stat().st_size
    hasher = sha256()
    with destination.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    checksum = hasher.hexdigest()
    duplicate = _find_duplicate(database, checksum)

    if duplicate is None and payload.existing_document_id is not None:
        duplicate = database.get(Document, str(payload.existing_document_id))

    if duplicate is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "The staged upload is no longer a duplicate of any "
                "stored document."
            ),
        )

    if payload.action == "use_existing":
        destination.unlink(missing_ok=True)
        try:
            delete_object(settings, destination.name)
        except Exception:
            pass

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
            message="Continuing with the existing document.",
            pipeline_log=["Reused the existing document"],
            approved_by=duplicate.approved_by,
            approved_at=duplicate.approved_at,
            source_status=source_status_for(
                settings, stored_filename=duplicate.stored_filename
            ),
            reused_existing=True,
        )

    log = ["Re-validated the staged file"]

    try:
        metadata = _extract_metadata(spec, destination)
        log.append(f"Extracted {spec.kind.upper()} metadata")

        size_bytes = destination.stat().st_size

        display_filename = sanitize_display_filename(
            payload.original_filename, extension=spec.extension
        )

        document, uploaded_at = _create_document_record(
            database=database,
            document_id=document_id,
            stored_filename=destination.name,
            display_filename=display_filename,
            content_type=spec.content_type,
            size_bytes=size_bytes,
            checksum=checksum,
            metadata=metadata,
        )
        upload_object(
            settings,
            destination.name,
            content_type=spec.content_type,
            file_path=destination,
            size_bytes=size_bytes,
        )

        log.append("Stored as a new document")

        if spec.kind in NATIVE_PAGE_KINDS:
            page_count = await run_in_threadpool(
                _ingest_native_pages,
                database,
                document_id,
                destination,
                spec,
            )
            metadata = PDFMetadata(
                page_count=page_count,
                encrypted=False,
                title=None,
                author=None,
            )
            log.append("Extracted document text")

        return UploadedDocumentResponse(
            document_id=document_id,
            original_filename=display_filename,
            status="ready",
            content_type=spec.content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            page_count=metadata.page_count,
            encrypted=metadata.encrypted,
            uploaded_at=uploaded_at,
            message="Uploaded as a new document alongside the existing one.",
            pipeline_log=log,
        )

    except (PDFValidationError, SecurityValidationError) as exc:
        destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        destination.unlink(missing_ok=True)
        database.rollback()

        raise HTTPException(
            status_code=500,
            detail="The file could not be stored securely.",
        ) from exc


@router.post(
    "/{document_id}/portfolio/select",
    response_model=UploadedDocumentResponse,
)
async def select_portfolio_file(
    document_id: UUID,
    payload: SelectPortfolioFileRequest,
    database: Session = Depends(get_database),
) -> UploadedDocumentResponse:
    staged = _find_staged_upload(document_id)

    if staged is None:
        raise HTTPException(
            status_code=404,
            detail="No pending portfolio upload found for this document id.",
        )

    destination, spec = staged

    if spec.kind != "pdf":
        raise HTTPException(
            status_code=409,
            detail="The staged upload is not a PDF Portfolio.",
        )

    log = ["Selected embedded document from PDF Portfolio"]

    try:
        extract_named_embedded_pdf(
            destination,
            filename=payload.filename,
            destination=destination,
        )
        log.append(f"Extracted embedded document '{payload.filename}'")

        metadata = _extract_metadata(spec, destination)
        log.append("Extracted PDF metadata")

        size_bytes = destination.stat().st_size
        hasher = sha256()
        with destination.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        checksum = hasher.hexdigest()

        duplicate = _find_duplicate(database, checksum)

        if duplicate is not None:
            return UploadedDocumentResponse(
                document_id=document_id,
                original_filename=duplicate.original_filename,
                status="duplicate_pending",
                content_type=spec.content_type,
                size_bytes=size_bytes,
                checksum_sha256=checksum,
                page_count=metadata.page_count,
                encrypted=metadata.encrypted,
                uploaded_at=datetime.now(timezone.utc),
                message=(
                    "A document with identical contents was already "
                    "uploaded. Choose whether to use the existing "
                    "document or upload this one anyway."
                ),
                duplicate=True,
                existing_document=_existing_document_summary(duplicate),
                pipeline_log=log,
            )

        display_filename = f"Portfolio → {payload.filename}"

        document, uploaded_at = _create_document_record(
            database=database,
            document_id=document_id,
            stored_filename=destination.name,
            display_filename=display_filename,
            content_type=spec.content_type,
            size_bytes=size_bytes,
            checksum=checksum,
            metadata=metadata,
        )
        upload_object(
            settings,
            destination.name,
            content_type=spec.content_type,
            file_path=destination,
            size_bytes=size_bytes,
        )

        log.append("Stored embedded document")

        return UploadedDocumentResponse(
            document_id=document_id,
            original_filename=display_filename,
            status="ready",
            content_type=spec.content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            page_count=metadata.page_count,
            encrypted=metadata.encrypted,
            uploaded_at=uploaded_at,
            message=(
                f"Extracted '{payload.filename}' from the PDF Portfolio "
                "for analysis."
            ),
            pipeline_log=log,
        )

    except (PDFValidationError, SecurityValidationError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        database.rollback()

        raise HTTPException(
            status_code=500,
            detail="The embedded document could not be stored securely.",
        ) from exc


def _document_field_value(
    database: Session, document_id: str, field_key: str
) -> str | None:
    row = database.scalar(
        select(DocumentMetadataField.value).where(
            DocumentMetadataField.document_id == document_id,
            DocumentMetadataField.field_key == field_key,
        )
    )

    return row or None


def _build_document_summary(
    database: Session, document: Document
) -> DocumentSummaryResponse:
    fields_extracted = database.scalar(
        select(func.count(DocumentMetadataField.id)).where(
            DocumentMetadataField.document_id == document.id
        )
    ) or 0

    latest_audit_change = database.scalar(
        select(func.max(MetadataFieldAuditLog.changed_at)).where(
            MetadataFieldAuditLog.document_id == document.id
        )
    )

    last_updated = (
        max(document.uploaded_at, latest_audit_change)
        if latest_audit_change
        else document.uploaded_at
    )

    counterparty = _document_field_value(
        database, document.id, "supplier"
    ) or _document_field_value(database, document.id, "customer")

    relationship: str | None = None

    if (
        document.parent_document_id
        and document.parent_relationship_status
        in {"confirmed", "manual"}
    ):
        parent_title = _document_field_value(
            database, document.parent_document_id, "contract_title"
        )
        relationship = f"Child of {parent_title or 'parent document'}"
    else:
        has_children = database.scalar(
            select(Document.id)
            .where(Document.parent_document_id == document.id)
            .limit(1)
        )

        if has_children is not None:
            relationship = "Parent"

    if document.promoted_at is not None:
        repository_status = "repository"
    elif document.approved_at is not None:
        repository_status = "approved"
    else:
        repository_status = "not_approved"

    settings = get_settings()

    return DocumentSummaryResponse(
        document_id=document.id,
        original_filename=document.original_filename,
        document_type=document.document_type,
        status=compute_document_status(database, document),
        confidence=compute_document_confidence(database, document),
        uploaded_at=document.uploaded_at,
        page_count=document.page_count,
        fields_extracted=fields_extracted,
        last_updated=last_updated,
        counterparty=counterparty,
        effective_date=_document_field_value(
            database, document.id, "effective_date"
        ),
        expiration_date=_document_field_value(
            database, document.id, "expiration_date"
        ),
        contract_value=_document_field_value(
            database, document.id, "contract_value"
        ),
        relationship=relationship,
        repository_status=repository_status,
        source_status=source_status_for(
            settings, stored_filename=document.stored_filename
        ),
    )


@router.get(
    "",
    response_model=list[DocumentSummaryResponse],
)
async def list_documents(
    limit: int = 10,
    database: Session = Depends(get_database),
) -> list[DocumentSummaryResponse]:
    documents = list(
        database.scalars(
            select(Document)
            .order_by(Document.uploaded_at.desc())
            .limit(limit)
        )
    )

    return [
        _build_document_summary(database, document)
        for document in documents
    ]


@router.delete(
    "/{document_id}",
    status_code=204,
)
async def delete_document(
    document_id: str,
    database: Session = Depends(get_database),
    actor: ActorContext = Depends(
        require_permission("documents.delete")
    ),
) -> Response:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    settings = get_settings()

    # Child documents (portfolio-extracted files) point back at this one
    # via parent_document_id, which has no ON DELETE CASCADE — detach
    # them first so they survive as standalone documents instead of
    # blocking the delete with a foreign-key violation.
    for child in database.scalars(
        select(Document).where(
            Document.parent_document_id == document_id
        )
    ):
        child.parent_document_id = None

    local_path = settings.upload_path / document.stored_filename
    if local_path.exists():
        local_path.unlink()

    try:
        delete_object(settings, document.stored_filename)
    except Exception:
        # Remote storage cleanup is best-effort — the document row and
        # its local file are the source of truth for whether it's gone.
        pass

    log_event(
        "document_deleted",
        document_id=document_id,
        original_filename=document.original_filename,
        actor_id=actor.id,
    )

    database.delete(document)
    database.commit()

    return Response(status_code=204)


@router.get(
    "/search",
    response_model=DocumentSearchResponse,
)
async def search_documents(
    q: str = "",
    status: str | None = None,
    document_type: str | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    repository_status: str | None = None,
    limit: int = 25,
    offset: int = 0,
    database: Session = Depends(get_database),
) -> DocumentSearchResponse:
    query = q.strip()
    settings = get_settings()
    scan_cap = max(50, int(settings.search_scan_cap))
    page_limit = max(1, min(limit, 100))
    page_offset = max(0, offset)

    matching_ids: set[str] | None = None

    if query:
        like = f"%{query}%"

        filename_matches = database.scalars(
            select(Document.id)
            .where(Document.original_filename.ilike(like))
            .limit(scan_cap)
        )

        field_matches = database.scalars(
            select(DocumentMetadataField.document_id)
            .where(
                DocumentMetadataField.field_key.in_(
                    [
                        "contract_number",
                        "contract_title",
                        "supplier",
                        "customer",
                    ]
                ),
                DocumentMetadataField.value.ilike(like),
            )
            .limit(scan_cap)
        )

        # Page-text search is the most expensive path — hard-cap matches.
        page_text_matches = database.scalars(
            select(DocumentPage.document_id)
            .where(DocumentPage.final_text.ilike(like))
            .limit(scan_cap)
        )

        matching_ids = (
            set(filename_matches)
            | set(field_matches)
            | set(page_text_matches)
        )

        if not matching_ids:
            return DocumentSearchResponse(documents=[], total=0)

    base_query = select(Document)

    if matching_ids is not None:
        base_query = base_query.where(Document.id.in_(matching_ids))

    if document_type:
        base_query = base_query.where(
            Document.document_type == document_type
        )

    needs_computed_filter = bool(
        status
        or confidence_min is not None
        or confidence_max is not None
        or repository_status
    )

    ordered = base_query.order_by(Document.uploaded_at.desc())

    if not needs_computed_filter:
        # Fast path: push pagination into SQL — no full-table materialize.
        total = (
            database.scalar(
                select(func.count()).select_from(
                    base_query.order_by(None).subquery()
                )
            )
            or 0
        )
        page_docs = list(
            database.scalars(
                ordered.offset(page_offset).limit(page_limit)
            )
        )
        summaries = [
            _build_document_summary(database, document)
            for document in page_docs
        ]
        return DocumentSearchResponse(documents=summaries, total=total)

    # Status / confidence / repository filters depend on computed summary
    # fields — scan a capped window instead of the entire repository.
    candidates = list(database.scalars(ordered.limit(scan_cap)))
    summaries = [
        _build_document_summary(database, document)
        for document in candidates
    ]

    if status:
        summaries = [
            summary for summary in summaries if summary.status == status
        ]

    if confidence_min is not None:
        summaries = [
            summary
            for summary in summaries
            if summary.confidence is not None
            and summary.confidence >= confidence_min
        ]

    if confidence_max is not None:
        summaries = [
            summary
            for summary in summaries
            if summary.confidence is not None
            and summary.confidence <= confidence_max
        ]

    if repository_status:
        summaries = [
            summary
            for summary in summaries
            if summary.repository_status == repository_status
        ]

    total = len(summaries)
    page = summaries[page_offset : page_offset + page_limit]

    return DocumentSearchResponse(documents=page, total=total)


@router.get(
    "/hierarchy",
    response_model=DocumentHierarchyResponse,
)
async def get_document_hierarchy(
    database: Session = Depends(get_database),
) -> DocumentHierarchyResponse:
    all_documents = list(database.scalars(select(Document)))

    children_by_parent: dict[str, list[Document]] = {}

    for document in all_documents:
        if document.parent_document_id is not None:
            children_by_parent.setdefault(
                document.parent_document_id, []
            ).append(document)

    def build_node(document: Document) -> HierarchyNode:
        title = (
            _document_field_value(
                database, document.id, "contract_title"
            )
            or document.original_filename
        )
        number = _document_field_value(
            database, document.id, "contract_number"
        )

        return HierarchyNode(
            document_id=document.id,
            title=title,
            document_number=number,
            document_type=document.document_type,
            relationship_type=document.parent_relationship_type,
            relationship_status=document.parent_relationship_status,
            children=[
                build_node(child)
                for child in children_by_parent.get(document.id, [])
            ],
        )

    roots = [
        build_node(document)
        for document in all_documents
        if document.parent_document_id is None
        and document.id in children_by_parent
    ]

    return DocumentHierarchyResponse(roots=roots)


@router.get(
    "/audit-log",
    response_model=GlobalAuditLogResponse,
)
async def get_global_audit_log(
    limit: int = 50,
    offset: int = 0,
    database: Session = Depends(get_database),
) -> GlobalAuditLogResponse:
    total = database.scalar(
        select(func.count(MetadataFieldAuditLog.id))
    ) or 0

    rows = list(
        database.scalars(
            select(MetadataFieldAuditLog)
            .order_by(MetadataFieldAuditLog.changed_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )

    document_ids = {row.document_id for row in rows}
    filenames = {
        document_id: filename
        for document_id, filename in database.execute(
            select(Document.id, Document.original_filename).where(
                Document.id.in_(document_ids)
            )
        )
    }

    entries = [
        GlobalAuditEntry(
            document_id=row.document_id,
            document_filename=filenames.get(
                row.document_id, "Unknown document"
            ),
            field_key=row.field_key,
            action=row.action,
            previous_value=row.previous_value,
            new_value=row.new_value,
            previous_status=row.previous_status,
            new_status=row.new_status,
            reason=row.reason,
            request_id=row.request_id,
            actor_id=row.actor_id,
            actor_type=row.actor_type,
            actor_role=row.actor_role,
            changed_by=row.changed_by,
            changed_at=row.changed_at,
        )
        for row in rows
    ]

    return GlobalAuditLogResponse(entries=entries, total=total)


@router.get(
    "/{document_id}",
    response_model=UploadedDocumentResponse,
)
async def get_document(
    document_id: str,
    database: Session = Depends(get_database),
) -> UploadedDocumentResponse:
    document = database.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return UploadedDocumentResponse(
        document_id=document.id,
        original_filename=document.original_filename,
        status=document.status,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        checksum_sha256=document.checksum_sha256,
        page_count=document.page_count,
        encrypted=document.encrypted,
        uploaded_at=document.uploaded_at,
        message="",
        approved_by=document.approved_by,
        approved_at=document.approved_at,
        promoted_by=document.promoted_by,
        promoted_at=document.promoted_at,
        source_status=source_status_for(
            get_settings(), stored_filename=document.stored_filename
        ),
        size_tier=(document.ingestion_provenance or {}).get("size_tier"),
        prefer_background=(document.ingestion_provenance or {}).get(
            "processing_mode"
        )
        == "background",
        processing_job_id=(document.ingestion_provenance or {}).get(
            "processing_job_id"
        ),
        ingestion_provenance=document.ingestion_provenance,
    )
