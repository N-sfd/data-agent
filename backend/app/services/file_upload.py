import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import UploadFile

from app.services.security_validation import (
    SecurityValidationError,
    UploadTypeSpec,
    resolve_upload_type,
    validate_content_type,
    validate_signature,
)

STREAM_CHUNK_SIZE = 1024 * 1024  # 1 MB


class UploadValidationError(Exception):
    """Raised when an uploaded file violates upload rules."""


@dataclass(frozen=True)
class SavedUpload:
    document_id: UUID
    stored_path: Path
    size_bytes: int
    checksum_sha256: str


def sanitize_display_filename(
    filename: str | None, *, extension: str = ".pdf"
) -> str:
    """
    Sanitize a filename for display and metadata storage.

    The sanitized client filename is never used as the physical
    server-side filename.
    """

    if not filename:
        return f"uploaded-document{extension}"

    filename = Path(filename).name
    filename = filename.replace("\x00", "")
    filename = re.sub(r"[\r\n\t]", " ", filename)
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    filename = filename[:150]

    if not filename:
        return f"uploaded-document{extension}"

    if not filename.lower().endswith(extension):
        filename = f"{filename}{extension}"

    return filename


def validate_upload_metadata(
    file: UploadFile,
) -> tuple[str, UploadTypeSpec]:
    """
    Validate an upload's declared filename/content-type before any bytes
    are read, returning the sanitized display filename and its resolved
    upload-type spec (PDF, DOCX, PNG, or JPG).
    """

    suffix = Path(file.filename or "").suffix.lower()

    try:
        spec = resolve_upload_type(suffix)
    except SecurityValidationError as exc:
        raise UploadValidationError(str(exc)) from exc

    original_filename = sanitize_display_filename(
        file.filename, extension=spec.extension
    )

    supplied_content_type = (
        file.content_type or "application/octet-stream"
    ).lower()

    try:
        validate_content_type(spec, supplied_content_type)
    except SecurityValidationError as exc:
        raise UploadValidationError(str(exc)) from exc

    return original_filename, spec


async def save_upload_stream(
    *,
    file: UploadFile,
    spec: UploadTypeSpec,
    document_id: UUID,
    destination: Path,
    max_size_bytes: int,
) -> SavedUpload:
    """
    Stream an already-validated upload to disk while enforcing the
    maximum size and confirming its magic-byte signature.
    """

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

                    try:
                        validate_signature(spec, chunk)
                    except SecurityValidationError as exc:
                        raise UploadValidationError(str(exc)) from exc

                total_size += len(chunk)

                if total_size > max_size_bytes:
                    raise UploadValidationError(
                        "The file exceeds the configured upload-size limit."
                    )

                sha256.update(chunk)
                await output_file.write(chunk)

        if total_size == 0:
            raise UploadValidationError(
                "The uploaded file is empty."
            )

        return SavedUpload(
            document_id=document_id,
            stored_path=destination,
            size_bytes=total_size,
            checksum_sha256=sha256.hexdigest(),
        )

    except Exception:
        destination.unlink(missing_ok=True)
        raise

    finally:
        await file.close()
