from dateutil import parser as dateutil_parser
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_metadata_field import DocumentMetadataField
from app.models.document_page import DocumentPage
from app.models.page_text_block import PageTextBlock
from app.schemas.contract_analysis import MetadataFieldResult
from app.schemas.universal_extraction import SourceEvidence
from app.services.ai_context import build_page_context
from app.services.ai_provider import AIProvider, AIProviderError
from app.services.contract_field_schema import (
    CODE_FIELD_PATTERNS,
    DATE_FIELD_KEYS,
    FIELD_SPECS,
    MONEY_FIELD_KEYS,
    FieldSpec,
)
from app.services.deterministic_extractor import source_evidence
from app.services.generic_entity_extractor import MONEY_PATTERN
from app.services.generic_label_extractor import (
    LayoutBlock,
    extract_labeled_value,
    extract_labeled_value_from_layout,
    normalize_label,
)
from app.services.document_outline import SectionBoundary, build_document_outline
from app.services.label_rejection import reject_as_field_value
from app.services.section_detection import section_for_value
from app.services.source_validator import validate_source_value


def _normalize_date(raw_value: str) -> str:
    try:
        parsed = dateutil_parser.parse(
            raw_value,
            fuzzy=True,
            default=None,
        )
    except (ValueError, OverflowError, TypeError):
        return raw_value

    return parsed.date().isoformat()


def _normalize_money(raw_value: str) -> str:
    match = MONEY_PATTERN.search(raw_value)

    if match:
        return match.group(0)

    return raw_value


def _normalize_code(field_key: str, raw_value: str) -> str:
    pattern = CODE_FIELD_PATTERNS.get(field_key)

    if pattern is None:
        return raw_value

    stripped = raw_value.strip()
    # Only normalize when the whole candidate is already the identifier.
    # Never silently carve an ID out of contaminated narrative OCR.
    match = pattern.fullmatch(stripped) or pattern.fullmatch(
        stripped.replace(" ", "")
    )
    if match:
        return match.group(0)

    return raw_value


def _normalize_field_value(
    field: FieldSpec, raw_value: str
) -> str:
    if field.key in DATE_FIELD_KEYS:
        return _normalize_date(raw_value)

    if field.key in MONEY_FIELD_KEYS:
        return _normalize_money(raw_value)

    if field.key in CODE_FIELD_PATTERNS:
        return _normalize_code(field.key, raw_value)

    return raw_value


def _load_blocks_by_page_id(
    *,
    database: Session,
    pages: list[DocumentPage],
) -> dict[int, list[LayoutBlock]]:
    page_ids = [page.id for page in pages]
    if not page_ids:
        return {}

    rows = database.scalars(
        select(PageTextBlock).where(
            PageTextBlock.document_page_id.in_(page_ids)
        )
    )

    blocks_by_page_id: dict[int, list[LayoutBlock]] = {}
    for row in rows:
        blocks_by_page_id.setdefault(row.document_page_id, []).append(
            LayoutBlock(
                text=row.text,
                x0=row.x0,
                y0=row.y0,
                x1=row.x1,
                y1=row.y1,
            )
        )

    return blocks_by_page_id


def _try_deterministic(
    *,
    field: FieldSpec,
    pages: list[DocumentPage],
    document_name: str,
    known_labels: frozenset[str] | None = None,
    blocks_by_page_id: dict[int, list[LayoutBlock]] | None = None,
    outline: list[SectionBoundary] | None = None,
) -> MetadataFieldResult | None:
    for page in pages:
        text = page.final_text or ""

        raw_value = extract_labeled_value_from_layout(
            blocks=(blocks_by_page_id or {}).get(page.id, []),
            requested_label=field.label,
            known_labels=known_labels,
        )
        # The regex fallback always runs too, even on pages flagged as
        # scanned — `is_scanned`/`requires_ocr` can be true for tiny/sparse
        # native-text pages (low text-coverage heuristics), and skipping
        # the fallback there means deterministic extraction silently loses
        # fields it used to resolve. `extract_labeled_value_from_layout`
        # already refuses to run on placeholder (all-zero) geometry, so it
        # costs nothing extra to also try the text-based path.
        if not raw_value:
            raw_value = extract_labeled_value(
                text=text,
                requested_label=field.label,
                known_labels=known_labels,
            )

        if not raw_value:
            continue
        if reject_as_field_value(raw_value, field_key=field.key):
            continue

        value = _normalize_field_value(field, raw_value)

        evidence = source_evidence(
            document_name=document_name,
            page_number=page.page_number,
            source_text=raw_value,
            section=section_for_value(
                outline,
                page_number=page.page_number,
                page_text=text,
                value=raw_value,
            ),
        )

        return MetadataFieldResult(
            field_group=field.group,
            field_key=field.key,
            label=field.label,
            value=value,
            confidence=0.80,
            extraction_method="label_value",
            evidence=evidence,
            verified=False,
        )

    return None


async def _resolve_with_ai(
    *,
    unresolved: list[FieldSpec],
    pages: list[DocumentPage],
    document_name: str,
    ai_provider: AIProvider,
    outline: list[SectionBoundary] | None = None,
) -> list[MetadataFieldResult]:
    if not unresolved or not pages:
        return []

    settings = get_settings()

    context = build_page_context(
        pages,
        maximum_characters=settings.ai_max_context_chars,
    )

    try:
        ai_result = await ai_provider.extract_fields(
            page_context=context,
            field_specs=unresolved,
        )
    except AIProviderError:
        # Deterministic fields already resolved should still be
        # returned even if the AI provider is unavailable.
        return []

    page_lookup = {
        page.page_number: page for page in pages
    }

    spec_lookup = {spec.key: spec for spec in unresolved}

    results: list[MetadataFieldResult] = []

    for raw_field in ai_result.get("fields", []):
        field_key = raw_field.get("field_key")
        spec = spec_lookup.get(field_key)

        if spec is None:
            continue

        page_number = raw_field.get("page_number")
        page = page_lookup.get(page_number)

        if page is None:
            continue

        value = str(raw_field.get("value", ""))
        source_text = raw_field.get("source_text", "")

        if reject_as_field_value(value, field_key=spec.key):
            continue

        if not validate_source_value(
            value=value,
            source_text=source_text,
            page_text=page.final_text or "",
        ):
            continue

        results.append(
            MetadataFieldResult(
                field_group=spec.group,
                field_key=spec.key,
                label=spec.label,
                value=value,
                confidence=float(
                    raw_field.get("confidence", 0.7)
                ),
                extraction_method="ai",
                evidence=SourceEvidence(
                    page_number=page_number,
                    source_text=source_text[:800],
                    source_reference=(
                        f"{document_name}, page {page_number}"
                    ),
                    section=section_for_value(
                        outline,
                        page_number=page_number,
                        page_text=page.final_text or "",
                        value=source_text,
                    ),
                ),
                verified=True,
            )
        )

    return results


async def extract_contract_metadata(
    *,
    database: Session,
    document: Document,
    pages: list[DocumentPage],
    ai_provider: AIProvider,
    extra_field_specs: list[FieldSpec] | None = None,
) -> list[MetadataFieldResult]:
    resolved: list[MetadataFieldResult] = []
    unresolved: list[FieldSpec] = []

    all_field_specs = list(FIELD_SPECS) + list(
        extra_field_specs or []
    )

    known_labels = frozenset(
        normalize_label(spec.label).lower() for spec in all_field_specs
    )

    blocks_by_page_id = _load_blocks_by_page_id(
        database=database, pages=pages
    )
    # Built once for the whole document — a UCF section spans many
    # pages, so every field resolves its section against this same
    # outline rather than each field re-deriving it independently.
    outline = build_document_outline(pages)

    for field in all_field_specs:
        match = _try_deterministic(
            field=field,
            pages=pages,
            document_name=document.original_filename,
            known_labels=known_labels,
            blocks_by_page_id=blocks_by_page_id,
            outline=outline,
        )

        if match:
            resolved.append(match)
        else:
            unresolved.append(field)

    ai_resolved = await _resolve_with_ai(
        unresolved=unresolved,
        pages=pages,
        document_name=document.original_filename,
        ai_provider=ai_provider,
        outline=outline,
    )

    resolved.extend(ai_resolved)

    database.execute(
        delete(DocumentMetadataField).where(
            DocumentMetadataField.document_id == document.id,
            DocumentMetadataField.extraction_source == "contract",
        )
    )

    for field in resolved:
        database.add(
            DocumentMetadataField(
                document_id=document.id,
                field_group=field.field_group,
                field_key=field.field_key,
                label=field.label,
                value=field.value,
                original_value=field.value,
                confidence=field.confidence,
                extraction_method=field.extraction_method,
                evidence_json=field.evidence.model_dump(),
                verified=field.verified,
                review_status="pending",
                extraction_source="contract",
            )
        )

    database.commit()

    return resolved


def get_metadata_field(
    database: Session,
    *,
    document_id: str,
    field_key: str,
) -> DocumentMetadataField | None:
    return database.scalar(
        select(DocumentMetadataField).where(
            DocumentMetadataField.document_id == document_id,
            DocumentMetadataField.field_key == field_key,
        )
    )


def field_to_result(
    field: DocumentMetadataField,
) -> MetadataFieldResult:
    """Reconstruct the API response shape from a persisted row."""

    return MetadataFieldResult(
        field_group=field.field_group,
        field_key=field.field_key,
        label=field.label,
        value=field.value,
        confidence=field.confidence,
        extraction_method=field.extraction_method,
        evidence=SourceEvidence(**field.evidence_json),
        verified=field.verified,
        review_status=field.review_status,
        original_value=field.original_value,
    )
