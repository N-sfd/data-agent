from pathlib import Path

import httpx

from app.core.config import Settings

REQUEST_TIMEOUT_SECONDS = 60.0


class DocumentStorageError(Exception):
    pass


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


def upload_object(
    settings: Settings,
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    """Back up a stored file's bytes to Supabase Storage. No-op when
    remote storage isn't configured (e.g. local development)."""

    if not is_remote_storage_configured(settings):
        return

    response = httpx.put(
        _object_url(settings, object_name),
        headers={
            **_headers(settings),
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        content=data,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code >= 400:
        raise DocumentStorageError(
            f"Failed to back up '{object_name}' to remote storage: "
            f"{response.text}"
        )


def _is_not_found_response(response: httpx.Response) -> bool:
    if response.status_code == 404:
        return True

    # Supabase Storage's API gateway wraps many object-store errors
    # (including a missing key) in an HTTP 400 response, with the
    # real status embedded in the JSON body instead of the header.
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
            f"{response.text}"
        )

    return response.content


def object_exists(settings: Settings, object_name: str) -> bool:
    if not is_remote_storage_configured(settings):
        return False

    # Streamed rather than a plain GET so a large file's bytes are never
    # pulled into memory just to answer an existence check; the error
    # body Supabase sends on a miss (see _is_not_found_response) is
    # small enough to read in full.
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
    """Check whether a stored file can still be recovered, either from
    Render's local disk or from the Supabase Storage backup."""

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


def ensure_local_copy(
    settings: Settings, *, stored_filename: str
) -> Path:
    """Return a local Path to the file, restoring it from Supabase
    Storage first if Render's ephemeral disk has already lost it."""

    local_path = settings.upload_path / stored_filename

    if local_path.exists():
        return local_path

    data = download_object(settings, stored_filename)

    if data is None:
        raise DocumentStorageError(
            "The original file for this document is no longer available "
            "on the server and was never backed up to remote storage. "
            "Please re-upload the document."
        )

    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)

    return local_path
