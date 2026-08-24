from typing import Any

from fastapi import HTTPException

UPLOAD_FAILED = "UPLOAD_FAILED"
PAGE_EXTRACTION_FAILED = "PAGE_EXTRACTION_FAILED"
OCR_FAILED = "OCR_FAILED"
STRUCTURE_DETECTION_FAILED = "STRUCTURE_DETECTION_FAILED"
TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
AI_PROVIDER_FAILED = "AI_PROVIDER_FAILED"
UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
UNSUPPORTED_DOCUMENT = "UNSUPPORTED_DOCUMENT"


def error_detail(
    code: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    return {"code": code, "message": message, **extra}


def http_error(
    status_code: int,
    code: str,
    message: str,
    **extra: Any,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=error_detail(code, message, **extra),
    )
