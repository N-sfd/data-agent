import asyncio
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import TARGET_NOT_FOUND, http_error
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.document_target import (
    DocumentTarget,
    ExtractTargetsResponse,
    ScalarTargetResult,
    TableTargetResult,
)
from app.services.ai_context import build_page_context
from app.services.ai_provider import AIProvider, AIProviderError
from app.services.ai_value_mapping import map_ai_value
from app.services.clause_citation_scanner import scan_pages_for_clause_citations
from app.services.confidence_engine import (
    compute_confidence,
    confidence_band,
    display_method,
)
from app.services.detected_target_store import load_document_targets
from app.services.form_field_search import search_form_fields
from app.services.generic_kv_scanner import is_internal_form_name
from app.services.generic_label_extractor import extract_labeled_value
from app.services.source_validator import validate_source_value

settings = get_settings()

_TABLE_LIKE_TYPES = {"table", "section", "clause"}
_MAX_CONCURRENT_AI_CALLS = 3

_KV_SOURCE_EVIDENCE = re.compile(
    r"^'(?P<label>[^:]+):\s*(?P<value>.+)'\s+on page\s+(?P<page>\d+)\s+\(",
)


def _resolve_scalar_from_source_examples(
    target: DocumentTarget,
    page_lookup: dict[int, DocumentPage],
) -> ScalarTargetResult | None:
    """Use discovery-time evidence before re-parsing page text."""
    for example in target.source_examples or []:
        match = _KV_SOURCE_EVIDENCE.match(example.strip())
        if not match:
            continue

        value = match.group("value").strip()
        if not value:
            continue

        page_number = int(match.group("page"))
        page = page_lookup.get(page_number)
        page_text = page.final_text if page else ""
        label = match.group("label").strip()
        snippet = f"{label}: {value}"

        verified = validate_source_value(
            value=value,
            source_text=snippet,
            page_text=page_text,
        )
        if not verified:
            continue

        confidence = compute_confidence(
            method="source_evidence",
            occurrence_count=target.occurrence_count,
            page=page,
        )

        return ScalarTargetResult(
            target=target.key,
            normalized_key=target.key,
            value=value,
            page=page_number,
            confidence=confidence,
            confidence_band=confidence_band(confidence),
            verified=True,
            extraction_method="source_evidence",
            display_method=display_method("source_evidence", page),
            evidence={
                "page_number": page_number,
                "source_text": snippet,
                "source_reference": f"page {page_number}",
            },
        )

    return None


def _resolve_scalar_target(
    target: DocumentTarget,
    page_lookup: dict[int, DocumentPage],
    all_pages: list[DocumentPage],
) -> ScalarTargetResult | None:
    from_evidence = _resolve_scalar_from_source_examples(target, page_lookup)
    if from_evidence is not None:
        return from_evidence

    candidate_pages = [
        page_lookup[number]
        for number in target.page_numbers
        if number in page_lookup
    ] or all_pages

    for page in candidate_pages:
        if page.form_fields_json:
            matches = search_form_fields(
                form_fields=page.form_fields_json,
                requested_concept=target.label,
            )
            if matches:
                name, value, score = matches[0]
                snippet = f"{name}: {value}"
                verified = validate_source_value(
                    value=value,
                    source_text=snippet,
                    page_text=page.final_text or "",
                )
                if not verified:
                    continue
                confidence = compute_confidence(
                    method="form_field",
                    match_exactness=score,
                    occurrence_count=target.occurrence_count,
                    page=page,
                )
                return ScalarTargetResult(
                    target=target.key,
                    normalized_key=target.key,
                    value=value,
                    page=page.page_number,
                    confidence=confidence,
                    confidence_band=confidence_band(confidence),
                    verified=verified,
                    extraction_method="form_field",
                    display_method=display_method("form_field", page),
                    evidence={
                        "page_number": page.page_number,
                        "source_text": snippet,
                        "source_reference": f"page {page.page_number}",
                    },
                )

        label_value = extract_labeled_value(
            text=page.final_text or "",
            requested_label=target.label,
        )
        if label_value:
            verified = validate_source_value(
                value=label_value,
                source_text=label_value,
                page_text=page.final_text or "",
            )
            if not verified:
                continue
            confidence = compute_confidence(
                method="label_value",
                occurrence_count=target.occurrence_count,
                page=page,
            )
            return ScalarTargetResult(
                target=target.key,
                normalized_key=target.key,
                value=label_value,
                page=page.page_number,
                confidence=confidence,
                confidence_band=confidence_band(confidence),
                verified=verified,
                extraction_method="label_value",
                display_method=display_method("label_value", page),
                evidence={
                    "page_number": page.page_number,
                    "source_text": label_value,
                    "source_reference": f"page {page.page_number}",
                },
            )

    return None


_CLAUSE_TARGET_KEYS = {"far_clauses", "dfars_clauses"}


def _resolve_clause_target(
    target: DocumentTarget,
    page_lookup: dict[int, DocumentPage],
    all_pages: list[DocumentPage],
) -> TableTargetResult | None:
    if target.target_type != "clause" and target.key not in _CLAUSE_TARGET_KEYS:
        return None

    candidate_pages = [
        page_lookup[number]
        for number in target.page_numbers
        if number in page_lookup
    ] or all_pages

    family_filter = None
    if target.key == "far_clauses":
        family_filter = "far_clauses"
    elif target.key == "dfars_clauses":
        family_filter = "dfars_clauses"

    citations = scan_pages_for_clause_citations(
        pages=candidate_pages,
        family_filter=family_filter,
    )
    if not citations:
        return None

    columns = ["clause_family", "clause_number", "title", "source_text", "page"]
    rows = [
        {
            "clause_family": citation.clause_family,
            "clause_number": citation.clause_number,
            "title": citation.title,
            "source_text": citation.source_text,
            "page": citation.page_number,
        }
        for citation in citations
    ]
    pages = sorted({citation.page_number for citation in citations})

    return TableTargetResult(
        target=target.key,
        columns=columns,
        rows=rows,
        pages=pages,
    )


def _headers_overlap(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 0.0
    set_a = {header.strip().lower() for header in a}
    set_b = {header.strip().lower() for header in b}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _resolve_table_target(
    target: DocumentTarget,
    page_lookup: dict[int, DocumentPage],
) -> TableTargetResult | None:
    candidate_pages = [
        page_lookup[number]
        for number in target.page_numbers
        if number in page_lookup
    ]

    for page in candidate_pages:
        for table in page.tables_json or []:
            headers = [str(header) for header in (table.get("headers") or [])]

            if target.columns:
                if _headers_overlap(headers, target.columns) < 0.5:
                    continue
            elif not headers:
                continue

            return TableTargetResult(
                target=target.key,
                columns=headers,
                rows=list(table.get("rows") or []),
                pages=[page.page_number],
            )

    return None


async def _run_batched_scalar_ai_fallback(
    *,
    targets: list[DocumentTarget],
    all_pages: list[DocumentPage],
    page_lookup: dict[int, DocumentPage],
    document_name: str,
    ai_provider: AIProvider,
) -> tuple[list[ScalarTargetResult], list[str]]:
    if not targets:
        return [], []

    label_list = "; ".join(f'"{target.label}"' for target in targets)
    instruction = f"Extract the following exact fields: {label_list}."
    context = build_page_context(
        all_pages, maximum_characters=settings.ai_max_context_chars
    )

    try:
        ai_result = await ai_provider.extract(
            instruction=instruction, page_context=context
        )
    except AIProviderError as exc:
        return [], [f"AI fallback unavailable: {exc}"]

    scalars: list[ScalarTargetResult] = []
    warnings: list[str] = []
    remaining = list(targets)

    for ai_value in ai_result.get("values", []):
        label = str(ai_value.get("label", "")).lower()

        matched = next(
            (
                target
                for target in remaining
                if target.label.lower() in label
                or label in target.label.lower()
            ),
            None,
        )
        if matched is None:
            continue

        value, warning = map_ai_value(
            ai_value=ai_value,
            page_lookup=page_lookup,
            document_name=document_name,
        )
        if warning:
            warnings.append(warning)
            continue

        ai_page = page_lookup.get(value.evidence.page_number)
        confidence = compute_confidence(
            method="ai",
            match_exactness=value.confidence,
            page=ai_page,
        )

        scalars.append(
            ScalarTargetResult(
                target=matched.key,
                normalized_key=matched.key,
                value=value.value,
                page=value.evidence.page_number,
                confidence=confidence,
                confidence_band=confidence_band(confidence),
                verified=value.verified,
                extraction_method="ai",
                display_method=display_method("ai", ai_page),
                evidence=value.evidence,
            )
        )
        remaining.remove(matched)

    # Never surface unverified AI values — they failed source validation.
    scalars = [item for item in scalars if item.verified]

    warnings.extend(ai_result.get("warnings", []))

    return scalars, warnings


async def _run_per_target_ai_fallback(
    *,
    target: DocumentTarget,
    all_pages: list[DocumentPage],
    page_lookup: dict[int, DocumentPage],
    document_name: str,
    ai_provider: AIProvider,
    semaphore: asyncio.Semaphore,
) -> tuple[TableTargetResult | ScalarTargetResult | None, list[str]]:
    async with semaphore:
        target_pages = [
            page_lookup[number]
            for number in target.page_numbers
            if number in page_lookup
        ] or all_pages

        instruction = (
            target.suggested_instruction or f"Extract the {target.label}."
        )
        context = build_page_context(
            target_pages, maximum_characters=settings.ai_max_context_chars
        )

        try:
            ai_result = await ai_provider.extract(
                instruction=instruction, page_context=context
            )
        except AIProviderError as exc:
            return None, [f"AI fallback unavailable for '{target.label}': {exc}"]

        warnings = list(ai_result.get("warnings", []))

        if target.target_type == "table":
            for ai_value in ai_result.get("values", []):
                raw_value = ai_value.get("value")
                if isinstance(raw_value, list) and raw_value:
                    columns = target.columns
                    if not columns and isinstance(raw_value[0], dict):
                        columns = list(raw_value[0].keys())
                    fallback_page = ai_value.get("page_number")
                    return (
                        TableTargetResult(
                            target=target.key,
                            columns=columns or [],
                            rows=raw_value,
                            pages=target.page_numbers
                            or ([fallback_page] if fallback_page else []),
                        ),
                        warnings,
                    )
            warnings.append(
                f"Could not extract table for '{target.label}'."
            )
            return None, warnings

        for ai_value in ai_result.get("values", []):
            value, warning = map_ai_value(
                ai_value=ai_value,
                page_lookup=page_lookup,
                document_name=document_name,
            )
            if warning:
                warnings.append(warning)
                continue
            if not value.verified:
                warnings.append(
                    f"AI result for '{target.label}' failed source validation."
                )
                continue
            ai_page = page_lookup.get(value.evidence.page_number)
            confidence = compute_confidence(
                method="ai",
                match_exactness=value.confidence,
                page=ai_page,
            )
            return (
                ScalarTargetResult(
                    target=target.key,
                    normalized_key=target.key,
                    value=value.value,
                    page=value.evidence.page_number,
                    confidence=confidence,
                    confidence_band=confidence_band(confidence),
                    verified=value.verified,
                    extraction_method="ai",
                    display_method=display_method("ai", ai_page),
                    evidence=value.evidence,
                ),
                warnings,
            )

        return None, warnings


async def extract_by_targets(
    *,
    database: Session,
    document: Document,
    target_ids: list[str],
    use_ai_fallback: bool,
    ai_provider: AIProvider,
) -> ExtractTargetsResponse:
    stored = load_document_targets(database=database, document_id=document.id)

    if stored is None:
        raise http_error(
            409,
            TARGET_NOT_FOUND,
            "Discover targets before extracting them.",
        )

    targets_by_id = {target.id: target for target in stored.targets}
    requested = [
        targets_by_id[target_id]
        for target_id in target_ids
        if target_id in targets_by_id
    ]
    unresolved: list[str] = [
        target_id for target_id in target_ids if target_id not in targets_by_id
    ]

    all_pages = list(
        database.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        )
    )
    page_lookup = {page.page_number: page for page in all_pages}

    scalars: list[ScalarTargetResult] = []
    tables: list[TableTargetResult] = []
    warnings: list[str] = []
    needs_ai: list[DocumentTarget] = []

    for target in requested:
        if target.target_type == "table":
            resolved_table = _resolve_table_target(target, page_lookup)
            if resolved_table is not None:
                tables.append(resolved_table)
                continue
        elif target.target_type == "clause" or target.key in _CLAUSE_TARGET_KEYS:
            resolved_clause = _resolve_clause_target(
                target, page_lookup, all_pages
            )
            if resolved_clause is not None:
                tables.append(resolved_clause)
                continue
        else:
            resolved_scalar = _resolve_scalar_target(
                target, page_lookup, all_pages
            )
            if resolved_scalar is not None:
                scalars.append(resolved_scalar)
                continue

        needs_ai.append(target)

    resolved_keys = {result.target for result in scalars} | {
        result.target for result in tables
    }

    if needs_ai and use_ai_fallback:
        batchable = [
            target
            for target in needs_ai
            if target.target_type not in _TABLE_LIKE_TYPES
        ]
        per_target = [
            target for target in needs_ai if target.target_type in _TABLE_LIKE_TYPES
        ]

        batched_scalars, batch_warnings = await _run_batched_scalar_ai_fallback(
            targets=batchable,
            all_pages=all_pages,
            page_lookup=page_lookup,
            document_name=document.original_filename,
            ai_provider=ai_provider,
        )
        scalars.extend(batched_scalars)
        warnings.extend(batch_warnings)
        resolved_keys.update(result.target for result in batched_scalars)

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_AI_CALLS)
        per_target_results = await asyncio.gather(
            *[
                _run_per_target_ai_fallback(
                    target=target,
                    all_pages=all_pages,
                    page_lookup=page_lookup,
                    document_name=document.original_filename,
                    ai_provider=ai_provider,
                    semaphore=semaphore,
                )
                for target in per_target
            ]
        )

        for result, target_warnings in per_target_results:
            warnings.extend(target_warnings)
            if result is None:
                continue
            if isinstance(result, TableTargetResult):
                tables.append(result)
            else:
                scalars.append(result)
            resolved_keys.add(result.target)

    still_unresolved: list[str] = list(unresolved)
    skipped_internal = 0
    for target in needs_ai:
        if target.key in resolved_keys:
            continue
        if is_internal_form_name(target.key) or is_internal_form_name(
            target.label or ""
        ):
            skipped_internal += 1
            continue
        still_unresolved.append(target.key)

    if skipped_internal:
        warnings.append(
            f"{skipped_internal} internal form field"
            f"{' was' if skipped_internal == 1 else 's were'} skipped "
            "because no readable value could be mapped."
        )

    return ExtractTargetsResponse(
        document_id=document.id,
        scalars=scalars,
        tables=tables,
        unresolved_targets=still_unresolved,
        warnings=warnings,
    )
