import re

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.structure_detection import (
    ContentStats,
    DetectedField,
    DetectedTable,
    StructureDetectionResponse,
)
from app.services.ai_provider import AIProvider
from app.services.contract_classifier import classify_contract
from app.services.generic_entity_extractor import (
    extract_generic_entities,
)
from app.services.generic_label_extractor import (
    extract_labeled_value,
)

# Pages beyond this aren't scanned for family/field detection — the
# same "the opening pages are almost always enough" reasoning already
# used by classify_contract, kept cheap for very long documents.
DETECTION_PAGE_LIMIT = 15

# key -> (label, keywords). Keywords are matched against a table's
# headers (joined) plus a little surrounding page text. Covers both
# financial-report tables and the existing contract-template families
# so a detected table can reuse the same label the static template
# picker already used, wherever the two overlap.
TABLE_FAMILIES: dict[str, tuple[str, list[str]]] = {
    "financial_summary": (
        "Financial Summary",
        ["financial summary", "total revenue", "total expenses",
         "net income", "summary of operations"],
    ),
    "revenue_analysis": (
        "Revenue Analysis",
        ["revenue analysis", "revenue by", "sales by", "revenue"],
    ),
    "operating_expenses": (
        "Operating Expenses",
        ["operating expense", "budget", "actual", "variance"],
    ),
    "accounts_payable": (
        "Accounts Payable Summary",
        ["accounts payable", "vendor", "open balance", "payable"],
    ),
    "rate_card": (
        "Rate Card",
        ["labor category", "hourly rate", "rate card", "billing rate"],
    ),
    "clins": (
        "CLINs",
        ["clin", "contract line item"],
    ),
    "pricing_table": (
        "Pricing Table",
        ["unit price", "total price", "pricing"],
    ),
    "payment_schedule": (
        "Payment Schedule",
        ["payment schedule", "due date", "installment"],
    ),
    "delivery_schedule": (
        "Delivery Schedule",
        ["delivery schedule", "milestone date", "delivery date"],
    ),
    "funding_table": (
        "Funding Table",
        ["funding", "allocation", "obligated amount"],
    ),
    "line_items": (
        "Line Items",
        ["line item", "description", "quantity"],
    ),
}

# key -> (label, keywords), scored against the document's opening text.
DOCUMENT_FAMILIES: dict[str, tuple[str, list[str]]] = {
    "financial_report": (
        "Financial Report",
        ["revenue", "operating expenses", "net income", "gross profit",
         "ebitda", "financial summary"],
    ),
    "invoice": (
        "Invoice",
        ["invoice number", "bill to", "remit to", "amount due",
         "invoice date"],
    ),
    "budget": (
        "Budget",
        ["budget vs actual", "budget", "variance", "fiscal year"],
    ),
    "statement": (
        "Statement",
        ["statement of account", "account statement",
         "beginning balance", "ending balance"],
    ),
    "purchase_order": (
        "Purchase Order",
        ["purchase order", "po number", "ship to"],
    ),
    "government_contract": (
        "Government Contract",
        ["clin", "far ", "dfars", "contracting officer",
         "cor/cotr", "solicitation"],
    ),
    "supplier_agreement": (
        "Supplier Agreement",
        ["supplier agreement", "vendor agreement"],
    ),
    "sow": (
        "Statement of Work",
        ["statement of work", "scope of work", "deliverables"],
    ),
    "amendment": (
        "Amendment",
        ["this amendment", "hereby amends", "amendment no"],
    ),
    "rate_card": (
        "Rate Card",
        ["rate card", "labor category", "hourly rate"],
    ),
    "contract": (
        "Contract",
        ["this agreement", "the parties", "effective date",
         "governing law", "whereas"],
    ),
}

# key -> (label, document field label to probe via extract_labeled_value).
FIELD_PROBES: list[tuple[str, str, str]] = [
    ("revenue", "Revenue", "Revenue"),
    ("gross_profit", "Gross Profit", "Gross Profit"),
    ("net_income", "Net Income", "Net Income"),
    ("operating_expenses", "Operating Expenses", "Operating Expenses"),
    ("contract_number", "Contract Number", "Contract Number"),
    ("effective_date", "Effective Date", "Effective Date"),
    ("invoice_number", "Invoice Number", "Invoice Number"),
    ("amount_due", "Amount Due", "Amount Due"),
    ("po_number", "PO Number", "PO Number"),
]

# Rough "N Corp / N Industries / N LLC" style organization mentions —
# a count for the unknown-document fallback, not a precision extractor.
ORGANIZATION_PATTERN = re.compile(
    r"\b(?:[A-Z][A-Za-z&.,]*\s+){1,4}"
    r"(?:Inc\.?|LLC|L\.L\.C\.|Corp\.?|Corporation|"
    r"Company|Co\.|Ltd\.?|Industries|Group|Partners)\b"
)

FAMILY_SCORE_MARGIN = 1
FAMILY_MIN_SCORE = 2
TABLE_MATCH_MIN_SCORE = 1


def _keyword_score(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _label_table(
    headers: list[str],
    surrounding_text: str,
    page_number: int,
    index: int,
) -> DetectedTable:
    haystack = (
        " ".join(headers) + " " + surrounding_text[:400]
    ).lower()

    best_key: str | None = None
    best_label = f"Table (page {page_number})"
    best_score = 0

    for key, (label, keywords) in TABLE_FAMILIES.items():
        score = _keyword_score(haystack, keywords)

        if score > best_score:
            best_key = key
            best_label = label
            best_score = score

    if best_score < TABLE_MATCH_MIN_SCORE:
        best_key = f"table_p{page_number}_{index}"

    confidence = min(0.99, 0.6 + 0.13 * best_score)

    return DetectedTable(
        key=best_key or f"table_p{page_number}_{index}",
        label=best_label,
        pages=[page_number],
        confidence=round(confidence, 2),
    )


def _merge_duplicate_tables(
    tables: list[DetectedTable],
) -> list[DetectedTable]:
    merged: dict[str, DetectedTable] = {}

    for table in tables:
        existing = merged.get(table.key)

        if existing is None:
            merged[table.key] = table
            continue

        existing.pages = sorted(set(existing.pages + table.pages))
        existing.confidence = max(existing.confidence, table.confidence)

    return list(merged.values())


def _classify_document_family(
    text: str,
) -> tuple[str, str, int]:
    lowered = text.lower()

    scores = {
        key: _keyword_score(lowered, keywords)
        for key, (_label, keywords) in DOCUMENT_FAMILIES.items()
    }

    ranked = sorted(
        scores.items(), key=lambda item: item[1], reverse=True
    )

    top_key, top_score = ranked[0]
    runner_up_score = ranked[1][1] if len(ranked) > 1 else 0

    if (
        top_score >= FAMILY_MIN_SCORE
        and top_score - runner_up_score >= FAMILY_SCORE_MARGIN
    ):
        label = DOCUMENT_FAMILIES[top_key][0]
        return top_key, label, top_score

    return "ambiguous", "Ambiguous", top_score


async def detect_document_structures(
    *,
    document: Document,
    pages: list[DocumentPage],
    ai_provider: AIProvider,
) -> StructureDetectionResponse:
    scan_pages = pages[:DETECTION_PAGE_LIMIT]
    combined_text = "\n".join(
        page.final_text or "" for page in scan_pages
    )

    # Tables
    detected_tables: list[DetectedTable] = []

    for page in scan_pages:
        for index, table in enumerate(page.tables_json or []):
            headers = table.get("headers") or []

            detected_tables.append(
                _label_table(
                    headers=headers,
                    surrounding_text=page.final_text or "",
                    page_number=page.page_number,
                    index=index,
                )
            )

    detected_tables = _merge_duplicate_tables(detected_tables)

    # Fields
    detected_fields: list[DetectedField] = []

    for key, label, probe_label in FIELD_PROBES:
        matching_pages = [
            page.page_number
            for page in scan_pages
            if extract_labeled_value(
                text=page.final_text or "",
                requested_label=probe_label,
            )
        ]

        if matching_pages:
            detected_fields.append(
                DetectedField(
                    key=key,
                    label=label,
                    pages=matching_pages,
                )
            )

    # Contacts (first pass — email/phone only)
    entities = extract_generic_entities(combined_text)
    detected_contacts = entities["email"] + entities["phone"]

    # Document family: deterministic first, AI only when ambiguous
    family_key, family_label, _score = _classify_document_family(
        combined_text
    )

    if family_key == "ambiguous":
        classification = await classify_contract(
            pages=scan_pages,
            ai_provider=ai_provider,
        )

        family_key, family_label = _map_contract_type_to_family(
            classification.document_type,
            classification.confidence,
        )

    # Content stats (always populated, including the unknown case)
    organizations = set(ORGANIZATION_PATTERN.findall(combined_text))

    content_stats = ContentStats(
        tables=len(detected_tables),
        dates=len(entities["date"]),
        currency_values=len(entities["money"]),
        organizations=len(organizations),
    )

    return StructureDetectionResponse(
        document_id=document.id,
        document_family=family_key,
        document_family_label=family_label,
        detected_fields=detected_fields,
        detected_tables=detected_tables,
        detected_contacts=detected_contacts,
        detected_obligations=[],
        content_stats=content_stats,
    )


def _map_contract_type_to_family(
    document_type: str,
    confidence: float,
) -> tuple[str, str]:
    if confidence < 0.4:
        return "unknown", "Unknown / General Document"

    mapping = {
        "Government Contract": "government_contract",
        "Supplier Agreement": "supplier_agreement",
        "Purchase Agreement": "purchase_order",
        "Purchase Order": "purchase_order",
        "Statement of Work": "sow",
        "Amendment": "amendment",
        "Change Order": "amendment",
    }

    contract_types = {
        "Master Services Agreement",
        "NDA",
        "Professional Services Agreement",
        "Software Agreement",
        "SaaS Agreement",
        "Lease",
        "Service Level Agreement",
        "License Agreement",
        "Consulting Agreement",
        "Construction Agreement",
        "Subcontract",
    }

    if document_type in mapping:
        key = mapping[document_type]
        return key, DOCUMENT_FAMILIES.get(
            key, (document_type, [])
        )[0]

    if document_type in contract_types:
        return "contract", DOCUMENT_FAMILIES["contract"][0]

    return "unknown", "Unknown / General Document"
