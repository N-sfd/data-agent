"""Processing / extraction version keys for artifact reuse.

Cached pages, schema, and extract results stay valid until the document
content fingerprint or a relevant processor version changes.
"""

from __future__ import annotations

from typing import Any

# Bump when pipeline semantics change in a way that requires reprocessing.
PAGES_PROCESSOR_VERSION = "pages-v1"
DISCOVERY_PROCESSOR_VERSION = "discovery-v2"
EXTRACTION_PROCESSOR_VERSION = "extraction-v3"


def document_content_fingerprint(document: Any) -> str:
    """Stable content key from checksum + page count."""

    checksum = getattr(document, "checksum_sha256", None) or ""
    pages = getattr(document, "page_count", None) or 0
    return f"{checksum}:{pages}"


def processing_versions_payload(
    *,
    document: Any,
    pages_version: str = PAGES_PROCESSOR_VERSION,
    discovery_version: str = DISCOVERY_PROCESSOR_VERSION,
    extraction_version: str = EXTRACTION_PROCESSOR_VERSION,
) -> dict[str, Any]:
    return {
        "content_fingerprint": document_content_fingerprint(document),
        "pages_processor_version": pages_version,
        "discovery_processor_version": discovery_version,
        "extraction_processor_version": extraction_version,
    }


def pages_artifacts_reusable(document: Any) -> bool:
    provenance = getattr(document, "ingestion_provenance", None) or {}
    if provenance.get("content_fingerprint") != document_content_fingerprint(
        document
    ):
        return False
    return (
        provenance.get("pages_processor_version") == PAGES_PROCESSOR_VERSION
    )


def discovery_artifacts_reusable(document: Any) -> bool:
    if not pages_artifacts_reusable(document):
        return False
    provenance = getattr(document, "ingestion_provenance", None) or {}
    return (
        provenance.get("discovery_processor_version")
        == DISCOVERY_PROCESSOR_VERSION
    )


def extraction_artifacts_reusable(document: Any) -> bool:
    if not discovery_artifacts_reusable(document):
        return False
    provenance = getattr(document, "ingestion_provenance", None) or {}
    return (
        provenance.get("extraction_processor_version")
        == EXTRACTION_PROCESSOR_VERSION
    )
