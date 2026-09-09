from datetime import datetime, timezone

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.document_target import (
    DiscoverSchemaResponse,
    DocumentTarget,
    TargetType,
)
from app.schemas.structure_detection import DetectedTarget
from app.services.ai_provider import AIProvider
from app.services.clin_block_detector import (
    RepeatedRecordBlock,
    detect_repeated_records,
)
from app.services.entity_classifier import classify_target_type
from app.services.generic_kv_scanner import is_internal_form_name
from app.services.structure_detection import (
    DETECTION_PAGE_LIMIT,
    KNOWN_TEMPLATE_KEYS,
    LITERAL_PHRASE_TEMPLATE_KEYS,
    detect_document_structures,
)


def _has_source_evidence(target: DetectedTarget) -> bool:
    """Detected = we can point to where it exists in the document."""
    if is_internal_form_name(target.key) or is_internal_form_name(target.label):
        return False

    if not target.evidence:
        return False

    if target.key in LITERAL_PHRASE_TEMPLATE_KEYS:
        required = LITERAL_PHRASE_TEMPLATE_KEYS[target.key]
        combined = " ".join(target.evidence).lower()
        if required not in combined:
            return False

    if target.extraction_type == "table" and target.key in KNOWN_TEMPLATE_KEYS:
        # Template tables need heading/column evidence, not a bare page mention.
        combined = " ".join(target.evidence).lower()
        if "unlabeled table" in combined and target.key in LITERAL_PHRASE_TEMPLATE_KEYS:
            return False

    return True


def _filter_evidence_backed(targets: list[DetectedTarget]) -> list[DetectedTarget]:
    return [target for target in targets if _has_source_evidence(target)]


def _sample_value_from_evidence(evidence: list[str]) -> str:
    if not evidence:
        return ""
    first = evidence[0]
    if ":" not in first:
        return ""
    return first.split(":", 1)[1].split("' on page", 1)[0].strip()


def _map_detected_target(
    target: DetectedTarget,
    *,
    document_id: str,
) -> DocumentTarget:
    target_type: TargetType = target.extraction_type

    if target.extraction_type == "field":
        sample_value = _sample_value_from_evidence(target.evidence)
        target_type = classify_target_type(target.label, sample_value)

    return DocumentTarget(
        id=f"{document_id}:{target.key}",
        key=target.key,
        label=target.label,
        target_type=target_type,
        page_numbers=target.pages,
        confidence=target.confidence,
        source_examples=target.evidence,
        columns=target.columns,
        suggested_instruction=target.suggested_prompt,
        source="detected",
    )


def _map_clin_block(
    block: RepeatedRecordBlock,
    *,
    document_id: str,
) -> DocumentTarget:
    return DocumentTarget(
        id=f"{document_id}:{block.key}",
        key=block.key,
        label=block.label,
        target_type="table",
        page_numbers=[block.page_number],
        confidence=0.9,
        source_examples=[
            f"{block.row_count} repeated rows on page {block.page_number}"
        ],
        columns=block.headers,
        occurrence_count=block.row_count,
        suggested_instruction=(
            f"Extract the {block.label} with all rows and columns."
        ),
        source="detected",
    )


def _dedupe_by_key(targets: list[DocumentTarget]) -> list[DocumentTarget]:
    merged: dict[str, DocumentTarget] = {}

    for target in targets:
        existing = merged.get(target.key)

        if existing is None:
            merged[target.key] = target
            continue

        existing.page_numbers = sorted(
            set(existing.page_numbers + target.page_numbers)
        )
        existing.confidence = max(existing.confidence, target.confidence)
        existing.occurrence_count = max(
            existing.occurrence_count, target.occurrence_count
        )
        if not existing.columns and target.columns:
            existing.columns = target.columns

    return list(merged.values())


def _count_by_type(targets: list[DocumentTarget]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for target in targets:
        counts[target.target_type] = counts.get(target.target_type, 0) + 1
    return counts


async def discover_document_schema(
    *,
    document: Document,
    pages: list[DocumentPage],
    ai_provider: AIProvider,
) -> DiscoverSchemaResponse:
    detection = await detect_document_structures(
        document=document,
        pages=pages,
        ai_provider=ai_provider,
    )

    primary_targets = _filter_evidence_backed(detection.detected_targets)

    # Promote high-value field-like possibles (KV / unlabeled document
    # labels) without reintroducing weak template table presets.
    for target in _filter_evidence_backed(detection.possible_targets):
        if target.extraction_type in {
            "field",
            "identifier",
            "date",
            "amount",
            "contact",
            "signature",
        }:
            primary_targets.append(target)
            continue

        if (
            target.extraction_type == "table"
            and target.key not in KNOWN_TEMPLATE_KEYS
            and target.key.startswith("table_p")
            and target.confidence >= 0.7
            and target.columns
        ):
            # Keep document-specific unlabeled tables with real columns.
            primary_targets.append(target)

    targets = [
        _map_detected_target(target, document_id=document.id)
        for target in primary_targets
    ]

    for page in pages[:DETECTION_PAGE_LIMIT]:
        for block in detect_repeated_records(page=page):
            targets.append(_map_clin_block(block, document_id=document.id))

    targets = _dedupe_by_key(targets)
    targets.sort(key=lambda item: (-item.confidence, item.key))

    return DiscoverSchemaResponse(
        document_id=document.id,
        document_family=detection.document_family,
        document_family_label=detection.document_family_label,
        document_family_confidence=detection.document_family_confidence,
        targets=targets,
        counts_by_type=_count_by_type(targets),
        generated_at=datetime.now(timezone.utc),
    )
