import zipfile
from dataclasses import dataclass
from pathlib import Path


class SecurityValidationError(Exception):
    """Raised when an uploaded file fails lightweight security checks.

    These are signature/extension/MIME allowlist checks, not antivirus
    scanning.
    """


@dataclass(frozen=True)
class UploadTypeSpec:
    kind: str
    extension: str
    content_type: str
    allowed_content_types: frozenset[str]
    signature: bytes


UPLOAD_TYPES: dict[str, UploadTypeSpec] = {
    ".pdf": UploadTypeSpec(
        kind="pdf",
        extension=".pdf",
        content_type="application/pdf",
        allowed_content_types=frozenset(
            {
                "application/pdf",
                "application/x-pdf",
                "application/octet-stream",
            }
        ),
        signature=b"%PDF-",
    ),
    ".docx": UploadTypeSpec(
        kind="docx",
        extension=".docx",
        content_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        allowed_content_types=frozenset(
            {
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document",
                "application/octet-stream",
                "application/zip",
            }
        ),
        signature=b"PK\x03\x04",
    ),
    ".png": UploadTypeSpec(
        kind="image",
        extension=".png",
        content_type="image/png",
        allowed_content_types=frozenset(
            {"image/png", "application/octet-stream"}
        ),
        signature=b"\x89PNG\r\n\x1a\n",
    ),
    ".jpg": UploadTypeSpec(
        kind="image",
        extension=".jpg",
        content_type="image/jpeg",
        allowed_content_types=frozenset(
            {"image/jpeg", "application/octet-stream"}
        ),
        signature=b"\xff\xd8\xff",
    ),
    ".jpeg": UploadTypeSpec(
        kind="image",
        extension=".jpeg",
        content_type="image/jpeg",
        allowed_content_types=frozenset(
            {"image/jpeg", "application/octet-stream"}
        ),
        signature=b"\xff\xd8\xff",
    ),
}


def resolve_upload_type(extension: str) -> UploadTypeSpec:
    spec = UPLOAD_TYPES.get(extension.lower())

    if spec is None:
        raise SecurityValidationError(
            "Unsupported file type. Supported types: "
            "PDF, DOCX, PNG, JPG."
        )

    return spec


def validate_signature(
    spec: UploadTypeSpec, first_chunk: bytes
) -> None:
    if not first_chunk.startswith(spec.signature):
        raise SecurityValidationError(
            "The file does not contain a valid "
            f"{spec.kind.upper()} signature."
        )


def validate_content_type(
    spec: UploadTypeSpec, content_type: str
) -> None:
    if content_type.lower() not in spec.allowed_content_types:
        raise SecurityValidationError(
            "The uploaded file has an unsupported content "
            "type for its extension."
        )


def validate_docx_structure(file_path: Path) -> None:
    """Confirm a .docx is a real OOXML word document, not just any zip."""

    try:
        with zipfile.ZipFile(file_path) as archive:
            if "word/document.xml" not in archive.namelist():
                raise SecurityValidationError(
                    "The file is a zip archive but not a "
                    "valid DOCX document."
                )
    except zipfile.BadZipFile as exc:
        raise SecurityValidationError(
            "The file does not contain a valid DOCX archive."
        ) from exc
