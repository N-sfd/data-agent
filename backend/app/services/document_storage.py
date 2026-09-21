"""Local disk cache + optional Supabase Storage backup."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from app.core.config import Settings
from app.core.observability import log_event

# Small objects keep a modest timeout; large backups need write headroom.
REQUEST_TIMEOUT_SECONDS = 60.0
LARGE_UPLOAD_TIMEOUT = httpx.Timeout(
    connect=30.0,
    read=120.0,
    write=600.0,
    pool=30.0,
)
LARGE_UPLOAD_BYTES = 10 * 1024 * 1024


class DocumentStorageError(Exception):
    """Remote or local document storage failure."""

    def __init__(
        self,
        message: str,
        *,
        error_type: str | None = None,
        http_status: int | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type or "DocumentStorageError"
        self.http_status = http_status


def is_remote_storage_configured(settings: Settings) -> bool:
    return bool(
        settings.supabase_url and settings.supabase_service_role_key
    )


def _object_url(settings: Settings, object_name: str) -> str:
    base = settings.supabase_url.rstrip("/")
    return (
        f"{base}/storage/v1/object/"
        f"{settings.supabase_storage_bucket}/{object_name}"
    )


def _headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.supabase_service_role_key}"}


def _timeout_for_size(size_bytes: int | None) -> float | httpx.Timeout:
    if size_bytes is not None and size_bytes >= LARGE_UPLOAD_BYTES:
        return LARGE_UPLOAD_TIMEOUT
    return REQUEST_TIMEOUT_SECONDS


def upload_object(
    settings: Settings,
    object_name: str,
    data: bytes | None = None,
    content_type: str = "application/octet-stream",
    *,
    file_path: Path | None = None,
    size_bytes: int | None = None,
) -> None:
    """Back up a stored file to Supabase Storage.

    Prefer ``file_path`` for medium/large uploads so the full body is not
    held in RAM. No-op when remote storage isn't configured.
    """

    if not is_remote_storage_configured(settings):
        return

    if file_path is None and data is None:
        raise DocumentStorageError(
            "upload_object requires data or file_path.",
            error_type="InvalidArgument",
        )

    resolved_size = size_bytes
    if resolved_size is None:
        if file_path is not None:
            resolved_size = file_path.stat().st_size
        elif data is not None:
            resolved_size = len(data)

    started = time.perf_counter()
    storage_provider = "supabase"
    http_status: int | None = None

    try:
        headers = {
            **_headers(settings),
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        # Supabase Storage (S3-compatible) rejects chunked bodies for many
        # large PUTs — always send Content-Length when size is known.
        if resolved_size is not None:
            headers["Content-Length"] = str(resolved_size)

        timeout = _timeout_for_size(resolved_size)

        if file_path is not None:
            with file_path.open("rb") as handle:
                response = httpx.put(
                    _object_url(settings, object_name),
                    headers=headers,
                    content=handle,
                    timeout=timeout,
                )
        else:
            response = httpx.put(
                _object_url(settings, object_name),
                headers=headers,
                content=data,
                timeout=timeout,
            )

        http_status = response.status_code
        if response.status_code >= 400:
            raise DocumentStorageError(
                f"Failed to back up '{object_name}' to remote storage "
                f"(HTTP {response.status_code}).",
                error_type="RemoteHttpError",
                http_status=response.status_code,
            )
    except DocumentStorageError as exc:
        log_event(
            "document_storage_failed",
            stage="document_storage",
            status="error",
            error_category=exc.error_type,
            size_bytes=resolved_size,
            content_type=content_type,
            storage_provider=storage_provider,
            error_type=exc.error_type,
            http_status=exc.http_status or http_status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            object_name=object_name,
        )
        raise
    except httpx.TimeoutException as exc:
        log_event(
            "document_storage_failed",
            stage="document_storage",
            status="error",
            error_category="Timeout",
            size_bytes=resolved_size,
            content_type=content_type,
            storage_provider=storage_provider,
            error_type=type(exc).__name__,
            http_status=http_status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            object_name=object_name,
        )
        raise DocumentStorageError(
            f"Timed out backing up '{object_name}' to remote storage.",
            error_type=type(exc).__name__,
        ) from exc
    except OSError as exc:
        log_event(
            "document_storage_failed",
            stage="document_storage",
            status="error",
            error_category="OSError",
            size_bytes=resolved_size,
            content_type=content_type,
            storage_provider=storage_provider,
            error_type=type(exc).__name__,
            http_status=http_status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            object_name=object_name,
        )
        raise DocumentStorageError(
            f"Local file error while backing up '{object_name}'.",
            error_type=type(exc).__name__,
        ) from exc
    except Exception as exc:
        log_event(
            "document_storage_failed",
            stage="document_storage",
            status="error",
            error_category=type(exc).__name__,
            size_bytes=resolved_size,
            content_type=content_type,
            storage_provider=storage_provider,
            error_type=type(exc).__name__,
            http_status=http_status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            object_name=object_name,
        )
        raise DocumentStorageError(
            f"Failed to back up '{object_name}' to remote storage.",
            error_type=type(exc).__name__,
        ) from exc


def _is_not_found_response(response: httpx.Response) -> bool:
    if response.status_code == 404:
        return True

    try:
        body = response.json()
    except ValueError:
        return False

    return (
        str(body.get("statusCode")) == "404"
        or body.get("error") in {"not_found", "NoSuchKey"}
    )


def download_object(
    settings: Settings, object_name: str
) -> bytes | None:
    if not is_remote_storage_configured(settings):
        return None

    response = httpx.get(
        _object_url(settings, object_name),
        headers=_headers(settings),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code >= 400:
        if _is_not_found_response(response):
            return None

        raise DocumentStorageError(
            f"Failed to fetch '{object_name}' from remote storage: "
            f"{response.text}",
            error_type="RemoteHttpError",
            http_status=response.status_code,
        )

    return response.content


def object_exists(settings: Settings, object_name: str) -> bool:
    if not is_remote_storage_configured(settings):
        return False

    with httpx.stream(
        "GET",
        _object_url(settings, object_name),
        headers=_headers(settings),
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        if response.status_code >= 400:
            response.read()
            return not _is_not_found_response(response)

        return True


def is_file_available(
    settings: Settings, *, stored_filename: str
) -> bool:
    local_path = settings.upload_path / stored_filename

    if local_path.exists():
        return True

    return object_exists(settings, stored_filename)


def delete_object(settings: Settings, object_name: str) -> None:
    if not is_remote_storage_configured(settings):
        return

    httpx.delete(
        _object_url(settings, object_name),
        headers=_headers(settings),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def classify_source_location(
    settings: Settings, *, stored_filename: str
) -> str:
    local_path = settings.upload_path / stored_filename

    if local_path.exists():
        return "local"

    if object_exists(settings, stored_filename):
        return "remote_only"

    return "missing"


def source_status_for(
    settings: Settings, *, stored_filename: str
) -> str:
    location = classify_source_location(
        settings, stored_filename=stored_filename
    )
    return "available" if location != "missing" else "missing"


def ensure_local_copy(
    settings: Settings, *, stored_filename: str
) -> Path:
    local_path = settings.upload_path / stored_filename

    if local_path.exists():
        return local_path

    data = download_object(settings, stored_filename)

    if data is None:
        raise DocumentStorageError(
            "Source file unavailable — re-upload required for source "
            "verification. Previously extracted data for this document is "
            "still available.",
            error_type="MissingOriginal",
        )

    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)

    return local_path
