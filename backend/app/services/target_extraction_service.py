"""Targeted extraction: retrieve → deterministic → AI escalate → validate."""

from __future__ import annotations

import asyncio
import re
from typing import Any

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
from app.schemas.extraction_intelligence import (
    ConfidenceDetail,
    RetrievalTrace,
    ValidationResult,
    confidence_detail_to_legacy_signals,
)
from app.services.ai_context import build_page_context
from app.services.ai_provider import AIProvider, AIProviderError
from app.services.ai_value_mapping import map_ai_value
from app.services.clause_citation_scanner import scan_pages_for_clause_citations
from app.services.confidence_engine import (
    display_method,
    explain_confidence,
)
from app.services.detected_target_store import load_document_targets
from app.services.form_field_search import search_form_fields
from app.services.generic_kv_scanner import is_internal_form_name
from app.services.generic_label_extractor import extract_labeled_value
from app.services.page_retrieval import (
    build_retrieval_trace,
    pages_from_trace,
)
from app.services.result_validation import build_validation_result
from app.services.review_routing import decide_review_for_scalar
from app.services.source_validator import validate_source_value

settings = get_settings()

_TABLE_LIKE_TYPES = {"table", "section", "clause"}
_MAX_CONCURRENT_AI_CALLS = 3

_KV_SOURCE_EVIDENCE = re.compile(
    r"^'(?P<label>[^:]+):\s*(?P<value>.+)'\s+on page\s+(?P<page>\d+)\s+\(",
)


def _scalar_result(
    *,
    target: DocumentTarget,
    value: Any,
    page_number: int,
    page: DocumentPage | None,
    method: str,
    confidence: ConfidenceDetail,
    validation: ValidationResult,
    evidence: dict[str, Any],
    retrieval: RetrievalTrace | None,
    verified: bool,
) -> ScalarTargetResult:
    scalar = ScalarTargetResult(
        target=target.key,
        normalized_key=target.key,
        value=value,
        extracted_value=value,
        review_status=None,  # filled after decide_review_for_scalar
        page=page_number,
        confidence=confidence.score,
        confidence_band=confidence.band,
        verified=verified,
        extraction_method=method,
        display_method=display_method(method, page),
        evidence=evidence,
        retrieval=retrieval,
        confidence_detail=confidence,
        validation=validation,
        confidence_signals=confidence_detail_to_legacy_signals(confidence),
        validation_status=validation.status,
    )
    decision = decide_review_for_scalar(scalar)
    return scalar.model_copy(
        update={
            "review_status": decision["review_status"],
            "review_decision": {
                "status": decision["status"],
                "priority": decision["priority"],
                "reasons": decision["reasons"],
            },
        }
    )


def _with_retrieval_status(
    trace: RetrievalTrace,
    *,
    deterministic_status: str,
    ai_fallback_required: bool,
) -> RetrievalTrace:
    return trace.model_copy(
        update={
            "deterministic_status": deterministic_status,
            "ai_fallback_required": ai_fallback_required,
        }
    )


def _resolve_scalar_from_source_examples(
    target: DocumentTarget,
    page_lookup: dict[int, DocumentPage],
    retrieval: RetrievalTrace | None = None,
) -> ScalarTargetResult | None:
    """Use discovery-time evidence before re-parsing page text."""
    if retrieval is None:
        retrieval = RetrievalTrace(
            target_key=target.key,
            candidate_pages=[],
            selected_pages=list(target.page_numbers or []),
            deterministic_status="not_attempted",
            ai_fallback_required=False,
        )
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

        validation = build_validation_result(
            value=value,
            value_type=target.value_type,
            source_text=snippet,
            page_text=page_text,
            source_presence_ok=True,
        )
        confidence = explain_confidence(
            method="source_evidence",
            occurrence_count=target.occurrence_count,
            page=page,
            source_grounded=True,
            validation_passed=validation.status == "passed",
            exact_label_match=True,
        )
        return _scalar_result(
            target=target,
            value=value,
            page_number=page_number,
            page=page,
            method="source_evidence",
            confidence=confidence,
            validation=validation,
            evidence={
                "page_number": page_number,
                "source_text": snippet,
                "source_reference": f"page {page_number}",
            },
            retrieval=_with_retrieval_status(
                retrieval,
                deterministic_status="resolved",
                ai_fallback_required=False,
            ),
            verified=True,
        )

    return None


def _resolve_scalar_target(
    target: DocumentTarget,
    page_lookup: dict[int, DocumentPage],
    all_pages: list[DocumentPage],
) -> tuple[ScalarTargetResult | None, RetrievalTrace, bool]:
    """Return (result, retrieval_trace, escalate_to_ai).

    escalate_to_ai is True when deterministic extraction is unresolved or
    ambiguous and AI should see the same retrieved evidence set.
    """

    retrieval = build_retrieval_trace(
        target=target,
        pages=all_pages,
        max_pages=settings.ai_max_pages,
    )

    from_evidence = _resolve_scalar_from_source_examples(
        target, page_lookup, retrieval
    )
    if from_evidence is not None:
        return from_evidence, from_evidence.retrieval or retrieval, False

    candidate_pages = pages_from_trace(
        trace=retrieval,
        page_lookup=page_lookup,
        all_pages=all_pages,
        max_pages=settings.ai_max_pages,
    )

    plausible: list[tuple[Any, ...]] = []

    for page in candidate_pages:
        if page.form_fields_json:
            matches = search_form_fields(
                form_fields=page.form_fields_json,
                requested_concept=target.label,
            )
            for name, value, score in matches[:3]:
                snippet = f"{name}: {value}"
                verified = validate_source_value(
                    value=value,
                    source_text=snippet,
                    page_text=page.final_text or "",
                )
                if verified:
                    plausible.append(
                        ("form_field", page, value, snippet, score, len(matches))
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
            if verified:
                plausible.append(
                    ("label_value", page, label_value, label_value, 0.9, 1)
                )

    if not plausible:
        retrieval = _with_retrieval_status(
            retrieval,
            deterministic_status="unresolved",
            ai_fallback_required=True,
        )
        return None, retrieval, True

    # Distinct values among strong candidates → escalate as ambiguous.
    distinct_values = {
        str(item[2]).strip().lower() for item in plausible if item[2] is not None
    }
    top_score = max(float(item[4]) for item in plausible)
    strong = [
        item
        for item in plausible
        if float(item[4]) >= max(0.7, top_score - 0.15)
    ]
    strong_values = {
        str(item[2]).strip().lower() for item in strong if item[2] is not None
    }

    if len(strong_values) > 1 or (len(distinct_values) > 1 and len(strong) > 1):
        retrieval = _with_retrieval_status(
            retrieval,
            deterministic_status="ambiguous",
            ai_fallback_required=True,
        )
        return None, retrieval, True

    method, page, value, snippet, score, match_count = plausible[0]
    validation = build_validation_result(
        value=value,
        value_type=target.value_type,
        source_text=snippet,
        page_text=page.final_text or "",
        source_presence_ok=True,
    )
    confidence = explain_confidence(
        method=method,
        match_exactness=float(score),
        occurrence_count=target.occurrence_count,
        page=page,
        source_grounded=True,
        validation_passed=validation.status == "passed",
        ambiguous_candidates=int(match_count),
        exact_label_match=method in {"form_field", "label_value"} and float(score) >= 0.9,
    )
    retrieval = _with_retrieval_status(
        retrieval,
        deterministic_status="resolved",
        ai_fallback_required=False,
    )
    return (
        _scalar_result(
            target=target,
            value=value,
            page_number=page.page_number,
            page=page,
            method=method,
            confidence=confidence,
            validation=validation,
            evidence={
                "page_number": page.page_number,
                "source_text": snippet,
                "source_reference": f"page {page.page_number}",
            },
            retrieval=retrieval,
            verified=True,
        ),
        retrieval,
        False,
    )


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


def _ai_scalar_from_value(
    *,
    target: DocumentTarget,
    value: Any,
    page_lookup: dict[int, DocumentPage],
    retrieval: RetrievalTrace | None,
) -> ScalarTargetResult | None:
    if not value.verified:
        return None
    ai_page = page_lookup.get(value.evidence.page_number)
    page_text = ai_page.final_text if ai_page else ""
    source_text = getattr(value.evidence, "source_text", "") or ""
    validation = build_validation_result(
        value=value.value,
        value_type=target.value_type,
        source_text=source_text,
        page_text=page_text or "",
        source_presence_ok=True,
    )
    confidence = explain_confidence(
        method="ai",
        match_exactness=value.confidence,
        page=ai_page,
        source_grounded=True,
        validation_passed=validation.status == "passed",
    )
    trace = None
    if retrieval is not None:
        trace = _with_retrieval_status(
            retrieval,
            deterministic_status=retrieval.deterministic_status
            if retrieval.deterministic_status != "not_attempted"
            else "unresolved",
            ai_fallback_required=True,
        )
    return _scalar_result(
        target=target,
        value=value.value,
        page_number=value.evidence.page_number,
        page=ai_page,
        method="ai",
        confidence=confidence,
        validation=validation,
        evidence=value.evidence,
        retrieval=trace,
        verified=True,
    )


async def _run_batched_scalar_ai_fallback(
    *,
    targets: list[DocumentTarget],
    retrieval_by_key: dict[str, RetrievalTrace],
    all_pages: list[DocumentPage],
    page_lookup: dict[int, DocumentPage],
    document_name: str,
    ai_provider: AIProvider,
) -> tuple[list[ScalarTargetResult], list[str]]:
    if not targets:
        return [], []

    # Union of ranked pages across the batch — never the full PDF.
    ranked_pages: list[DocumentPage] = []
    seen_pages: set[int] = set()
    for target in targets:
        trace = retrieval_by_key.get(target.key) or build_retrieval_trace(
            target=target,
            pages=all_pages,
            max_pages=settings.ai_max_pages,
        )
        for page in pages_from_trace(
            trace=trace,
            page_lookup=page_lookup,
            all_pages=all_pages,
            max_pages=settings.ai_max_pages,
        ):
            if page.page_number in seen_pages:
                continue
            seen_pages.add(page.page_number)
            ranked_pages.append(page)
            if len(ranked_pages) >= settings.ai_max_pages:
                break
        if len(ranked_pages) >= settings.ai_max_pages:
            break

    label_list = "; ".join(f'"{target.label}"' for target in targets)
    instruction = f"Extract the following exact fields: {label_list}."
    context = build_page_context(
        ranked_pages or all_pages[: settings.ai_max_pages],
        maximum_characters=settings.ai_max_context_chars,
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

        scalar = _ai_scalar_from_value(
            target=matched,
            value=value,
            page_lookup=page_lookup,
            retrieval=retrieval_by_key.get(matched.key),
        )
        if scalar is None:
            continue
        scalars.append(scalar)
        remaining.remove(matched)

    warnings.extend(ai_result.get("warnings", []))
    return scalars, warnings


async def _run_per_target_ai_fallback(
    *,
    target: DocumentTarget,
    retrieval: RetrievalTrace | None,
    all_pages: list[DocumentPage],
    page_lookup: dict[int, DocumentPage],
    document_name: str,
    ai_provider: AIProvider,
    semaphore: asyncio.Semaphore,
) -> tuple[TableTargetResult | ScalarTargetResult | None, list[str]]:
    async with semaphore:
        trace = retrieval or build_retrieval_trace(
            target=target,
            pages=all_pages,
            max_pages=settings.ai_max_pages,
        )
        target_pages = pages_from_trace(
            trace=trace,
            page_lookup=page_lookup,
            all_pages=all_pages,
            max_pages=settings.ai_max_pages,
        )

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
            scalar = _ai_scalar_from_value(
                target=target,
                value=value,
                page_lookup=page_lookup,
                retrieval=trace,
            )
            if scalar is not None:
                return scalar, warnings

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
    retrieval_by_key: dict[str, RetrievalTrace] = {}

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
            resolved_scalar, retrieval, escalate = _resolve_scalar_target(
                target, page_lookup, all_pages
            )
            retrieval_by_key[target.key] = retrieval
            if resolved_scalar is not None:
                scalars.append(resolved_scalar)
                continue
            if escalate:
                needs_ai.append(target)
                continue

        needs_ai.append(target)
        if target.key not in retrieval_by_key:
            retrieval_by_key[target.key] = build_retrieval_trace(
                target=target,
                pages=all_pages,
                max_pages=settings.ai_max_pages,
            )
            retrieval_by_key[target.key] = _with_retrieval_status(
                retrieval_by_key[target.key],
                deterministic_status="unresolved",
                ai_fallback_required=True,
            )

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
            retrieval_by_key=retrieval_by_key,
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
                    retrieval=retrieval_by_key.get(target.key),
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
