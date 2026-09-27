"""Cross-page table continuation hints (not merging).

A table that ends near the bottom of page N and one that starts near the
top of page N+1 with the same column count — and either the same header
signature or no header row of its own — are linked as continuation
candidates. Nothing is merged: that judgement belongs to the profile that
consumes the rows.
"""

from __future__ import annotations

import re

from app.source_structure.models import TableCandidate, TableContinuation

_NEAR_TOP = 0.30
_NEAR_BOTTOM = 0.70


def _normalize_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (header or "").lower()).strip()


def annotate_geometry(table: TableCandidate, page_height: float | None) -> None:
    has_header = bool(table.header_cells)
    headers = [_normalize_header(h) for h in table.headers] if has_header else []
    column_count = len(table.headers)
    top = bottom = None
    if table.bbox and page_height:
        top = round(table.bbox[1] / page_height, 3)
        bottom = round(table.bbox[3] / page_height, 3)
    table.continuation = TableContinuation(
        normalized_headers=headers,
        header_signature="|".join(headers) if headers else f"columns:{column_count}",
        column_count=column_count,
        page_top_ratio=top,
        page_bottom_ratio=bottom,
        starts_near_page_top=top is not None and top <= _NEAR_TOP,
        ends_near_page_bottom=bottom is not None and bottom >= _NEAR_BOTTOM,
    )


def link_continuations(tables: list[TableCandidate]) -> None:
    by_page: dict[int, list[TableCandidate]] = {}
    for table in tables:
        if table.page is not None and table.continuation is not None and table.acceptance == "accepted":
            by_page.setdefault(table.page, []).append(table)

    # A continuation page without its own header row carries the header of
    # the table it continues, so a later page repeating that header still
    # matches the chain.
    effective_signature: dict[str, str] = {
        t.candidate_id: t.continuation.header_signature for ts in by_page.values() for t in ts
    }
    for page in sorted(by_page):
        page_tables = by_page[page]
        last = max(page_tables, key=lambda t: t.bbox[3] if t.bbox else 0)
        following = by_page.get(page + 1)
        if not following or not last.continuation.ends_near_page_bottom:
            continue
        first = min(following, key=lambda t: t.bbox[1] if t.bbox else 0)
        prev_c, next_c = last.continuation, first.continuation
        if not next_c.starts_near_page_top or prev_c.column_count != next_c.column_count:
            continue
        chain_signature = effective_signature[last.candidate_id]
        if next_c.normalized_headers and next_c.header_signature == chain_signature:
            reason = "repeated_header_on_next_page"
        elif not next_c.normalized_headers:
            reason = "next_page_table_has_no_header_row"
            effective_signature[first.candidate_id] = chain_signature
        else:
            continue
        prev_c.continuation_candidate = next_c.continuation_candidate = True
        prev_c.next_candidate_id = first.candidate_id
        next_c.previous_candidate_id = last.candidate_id
        prev_c.hint_reasons.append(f"continues_on_page_{page + 1}:{reason}")
        next_c.hint_reasons.append(f"continues_from_page_{page}:{reason}")
