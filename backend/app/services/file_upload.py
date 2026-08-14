import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import UploadFile


PDF_SIGNATURE = b"%PDF-"
STREAM_CHUNK_SIZE = 1024 * 1024  # 1 MB

ALLOWED_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
}


class UploadValidationError(Exception):
    """Raised when an uploaded file violates upload rules."""


@dataclass(frozen=True)
class SavedUpload:
    document_id: UUID
    original_filename: str
    stored_path: Path
    size_bytes: int
    checksum_sha256: str


def sanitize_display_filename(filename: str | None) -> str:
    """
    Sanitize a filename for display and metadata storage.

    The sanitized client filename is never used as the physical
    server-side filename.
    """

    if not filename:
        return "uploaded-document.pdf"

    filename = Path(filename).name
    filename = filename.replace("\x00", "")
    filename = re.sub(r"[\r\n\t]", " ", filename)
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    filename = filename[:150]

    if not filename:
        return "uploaded-document.pdf"

    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"

    return filename


def validate_upload_metadata(file: UploadFile) -> str:
    original_filename = sanitize_display_filename(file.filename)

    suffix = Path(original_filename).suffix.lower()

    if suffix != ".pdf":
        raise UploadValidationError(
            "Only PDF documents are supported."
        )

    supplied_content_type = (
        file.content_type or "application/octet-stream"
    ).lower()

    if supplied_content_type not in ALLOWED_PDF_CONTENT_TYPES:
        raise UploadValidationError(
            "The uploaded file has an unsupported content type."
        )

    return original_filename


async def save_pdf_stream(
    *,
    file: UploadFile,
    document_id: UUID,
    destination: Path,
    max_size_bytes: int,
) -> SavedUpload:
    """
    Stream an uploaded PDF to disk while enforcing the maximum size.

    The first bytes are checked before the upload is accepted as a PDF.
    """

    original_filename = validate_upload_metadata(file)
    sha256 = hashlib.sha256()
    total_size = 0
    first_chunk = True

    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with aiofiles.open(destination, "xb") as output_file:
            while True:
                chunk = await file.read(STREAM_CHUNK_SIZE)

                if not chunk:
                    break

                if first_chunk:
                    first_chunk = False

                    if not chunk.startswith(PDF_SIGNATURE):
                        raise UploadValidationError(
                            "The file does not contain a valid PDF signature."
                        )

                total_size += len(chunk)

                if total_size > max_size_bytes:
                    raise UploadValidationError(
                        "The PDF exceeds the configured upload-size limit."
                    )

                sha256.update(chunk)
                await output_file.write(chunk)

        if total_size == 0:
            raise UploadValidationError(
                "The uploaded PDF is empty."
            )

        return SavedUpload(
            document_id=document_id,
            original_filename=original_filename,
            stored_path=destination,
            size_bytes=total_size,
            checksum_sha256=sha256.hexdigest(),
        )

    except Exception:
        destination.unlink(missing_ok=True)
        raise

    finally:
        await file.close()
