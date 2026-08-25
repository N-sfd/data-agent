import re
from dataclasses import dataclass

from app.models.document import Document
from app.models.document_page import DocumentPage
from app.schemas.structure_detection import (
    ContentStats,
    DetectedField,
    DetectedTable,
    DetectedTarget,
    DetectionCounts,
    ExtractionType,
    StructureDetectionResponse,
)
from app.services.ai_provider import AIProvider, AIProviderError
from app.services.contract_classifier import classify_contract
from app.services.generic_entity_extractor import (
    extract_generic_entities,
)
from app.services.generic_kv_scanner import scan_page_for_labeled_pairs
from app.services.generic_label_extractor import (
    extract_labeled_value,
)

DETECTION_PAGE_LIMIT = 15

PRIMARY_CONFIDENCE_MIN = 0.75
HIGH_CONFIDENCE_MIN = 0.90

FAMILY_SCORE_MARGIN = 1
FAMILY_MIN_SCORE = 2
TABLE_MATCH_MIN_SCORE = 2

# Preferred defaults when several tables are equally plausible.
FAMILY_DEFAULT_KEYS: dict[str, list[str]] = {
    "financial_report": [
        "operating_expenses",
        "revenue_analysis",
        "financial_summary",
        "accounts_payable",
    ],
    "budget": [
        "operating_expenses",
        "budget_vs_actual",
        "financial_summary",
    ],
    "government_contract": ["clins", "rate_card", "pricing_table"],
    "rate_card": ["rate_card", "labor_categories", "hourly_rates"],
}


@dataclass(frozen=True)
class HeadingFamily:
    key: str
    label: str
    pattern: re.Pattern[str]
    extraction_type: ExtractionType
    suggested_prompt: str


HEADING_FAMILIES: list[HeadingFamily] = [
    HeadingFamily(
        "financial_summary",
        "Financial Summary",
        re.compile(r"financial\s+summary", re.I),
        "table",
        "Extract the financial summary table.",
    ),
    HeadingFamily(
        "revenue_analysis",
        "Revenue Analysis",
        re.compile(r"revenue\s+analysis", re.I),
        "table",
        "Extract the revenue analysis table with budget, actual, and variance.",
    ),
    HeadingFamily(
        "operating_expenses",
        "Operating Expenses",
        re.compile(r"operating\s+expenses?", re.I),
        "table",
        "Extract operating expenses with budget, actual, variance, and variance percentage.",
    ),
    HeadingFamily(
        "accounts_payable",
        "Accounts Payable Summary",
        re.compile(r"accounts\s+payable", re.I),
        "table",
        "Extract vendor invoice counts and open balances.",
    ),
    HeadingFamily(
        "budget_vs_actual",
        "Budget vs Actual",
        re.compile(r"budget\s+vs\.?\s+actual", re.I),
        "table",
        "Extract the budget vs actual table with variance columns.",
    ),
    HeadingFamily(
        "vendor_balances",
        "Vendor Balances",
        re.compile(r"vendor\s+balances?", re.I),
        "table",
        "Extract vendor balances and open amounts.",
    ),
    HeadingFamily(
        "rate_card",
        "Rate Card",
        re.compile(r"rate\s+card", re.I),
        "table",
        "Extract the rate card with labor categories and hourly rates.",
    ),
    HeadingFamily(
        "labor_categories",
        "Labor Categories",
        re.compile(r"labor\s+categor", re.I),
        "table",
        "Extract labor categories and associated rates.",
    ),
    HeadingFamily(
        "hourly_rates",
        "Hourly Rates",
        re.compile(r"hourly\s+rates?", re.I),
        "table",
        "Extract hourly rates by labor category.",
    ),
    HeadingFamily(
        "clins",
        "CLINs",
        re.compile(r"\bclins?\b|contract\s+line\s+item", re.I),
        "table",
        "Extract all CLINs with quantities, unit prices, total prices, and descriptions.",
    ),
    HeadingFamily(
        "pricing_table",
        "Pricing Table",
        # "unit price" alone is too generic — it also appears in ordinary
        # supplies/services and line-item tables. Only match the literal
        # heading phrase.
        re.compile(r"pricing\s+table", re.I),
        "table",
        "Extract the full pricing table with all line items and amounts.",
    ),
    HeadingFamily(
        "payment_schedule",
        "Payment Schedule",
        re.compile(r"payment\s+schedule", re.I),
        "table",
        "Extract the payment schedule with due dates and amounts.",
    ),
    HeadingFamily(
        "delivery_schedule",
        "Delivery Schedule",
        re.compile(r"delivery\s+schedule", re.I),
        "table",
        "Extract the delivery schedule with milestones and dates.",
    ),
    HeadingFamily(
        "far_clauses",
        "FAR Clauses",
        re.compile(r"\bfar\s+52\.|federal\s+acquisition\s+regulation", re.I),
        "clause",
        "Extract FAR clauses cited in this document.",
    ),
    HeadingFamily(
        "dfars_clauses",
        "DFARS Clauses",
        re.compile(r"\bdfars\s+252\.", re.I),
        "clause",
        "Extract DFARS clauses cited in this document.",
    ),
    HeadingFamily(
        "payment_obligations",
        "Payment Obligations",
        re.compile(r"payment\s+obligations?", re.I),
        "obligation",
        "Extract all payment obligations and terms.",
    ),
    HeadingFamily(
        "reporting_requirements",
        "Reporting Requirements",
        re.compile(r"reporting\s+requirements?", re.I),
        "obligation",
        "Extract all reporting requirements and their frequency.",
    ),
    HeadingFamily(
        "signatures",
        "Signatures",
        re.compile(
            r"in\s+witness\s+whereof|\bsignature\s+block\b|\bsigned\s+by\b",
            re.I,
        ),
        "signature",
        "Extract signatory names, titles, and signature dates.",
    ),
    HeadingFamily(
        "supplies_services",
        "Supplies / Services",
        re.compile(r"supplies\s*(?:/|or)\s*services", re.I),
        "table",
        "Extract the supplies/services table with item numbers, quantities, "
        "units, unit prices, and amounts.",
    ),
    HeadingFamily(
        "clin_delivery_schedule",
        "CLIN Delivery Schedule",
        re.compile(
            r"clin.{0,40}delivery\s+schedule|delivery\s+schedule.{0,40}clin",
            re.I,
        ),
        "table",
        "Extract the CLIN delivery schedule with delivery dates, quantities, "
        "and ship-to addresses.",
    ),
    HeadingFamily(
        "wawf_routing_data",
        "WAWF Routing Data",
        re.compile(r"wawf\s+routing\s+data|wide\s+area\s+workflow", re.I),
        "table",
        "Extract the complete WAWF Routing Data table, preserving all "
        "detected columns and rows.",
    ),
    HeadingFamily(
        "clauses_incorporated_by_reference",
        "Clauses Incorporated by Reference",
        re.compile(r"clauses\s+incorporated\s+by\s+reference", re.I),
        "clause",
        "Extract all clauses listed under \"CLAUSES INCORPORATED BY "
        "REFERENCE\", including clause number, title, date/version, and "
        "source page where available.",
    ),
    HeadingFamily(
        "clauses_incorporated_full_text",
        "Clauses Incorporated by Full Text",
        re.compile(r"clauses\s+incorporated\s+by\s+full\s+text", re.I),
        "clause",
        "Extract all clauses listed under \"CLAUSES INCORPORATED BY FULL "
        "TEXT\", including clause number, title, and full clause text.",
    ),
]


# Headers / surrounding text only — no single-word keywords that would
# label every financial table as "Revenue" or every budget column as
# "Operating Expenses".
TABLE_FAMILIES: dict[str, tuple[str, list[str]]] = {
    "financial_summary": (
        "Financial Summary",
        ["financial summary", "total revenue", "net income",
         "summary of operations"],
    ),
    "revenue_analysis": (
        "Revenue Analysis",
        ["revenue analysis", "revenue by", "sales by"],
    ),
    "operating_expenses": (
        "Operating Expenses",
        ["operating expense", "expense category"],
    ),
    "accounts_payable": (
        "Accounts Payable Summary",
        ["accounts payable", "open balance"],
    ),
    "budget_vs_actual": (
        "Budget vs Actual",
        ["budget vs actual", "budget versus actual"],
    ),
    "vendor_balances": (
        "Vendor Balances",
        ["vendor balance", "vendor balances"],
    ),
    "rate_card": (
        "Rate Card",
        ["labor category", "hourly rate", "rate card", "billing rate"],
    ),
    "labor_categories": (
        "Labor Categories",
        ["labor category", "labor categories"],
    ),
    "hourly_rates": (
        "Hourly Rates",
        ["hourly rate", "hourly rates"],
    ),
    "clins": (
        "CLINs",
        ["clin", "contract line item"],
    ),
    "pricing_table": (
        "Pricing Table",
        # "unit price"/"total price" alone are too generic — they also
        # appear in ordinary supplies/services or line-item tables that
        # aren't labeled "Pricing Table" anywhere in the document. Only
        # match when the document itself uses the term.
        ["pricing table"],
    ),
    "payment_schedule": (
        "Payment Schedule",
        ["payment schedule", "installment"],
    ),
    "delivery_schedule": (
        "Delivery Schedule",
        ["delivery schedule", "milestone date"],
    ),
    "funding_table": (
        "Funding Table",
        ["funding table", "obligated amount"],
    ),
    "line_items": (
        "Line Items",
        ["line item"],
    ),
    "supplies_services": (
        "Supplies / Services",
        ["supplies or services", "supplies/services",
         "schedule of supplies"],
    ),
    "clin_delivery_schedule": (
        "CLIN Delivery Schedule",
        ["clin", "delivery schedule", "delivery date"],
    ),
    "wawf_routing_data": (
        "WAWF Routing Data",
        ["wawf", "routing data", "dodaac"],
    ),
    "clauses_incorporated_by_reference": (
        "Clauses Incorporated by Reference",
        ["incorporated by reference", "clauses incorporated"],
    ),
    "clauses_incorporated_full_text": (
        "Clauses Incorporated by Full Text",
        ["incorporated by full text", "full text clauses"],
    ),
}


DOCUMENT_FAMILIES: dict[str, tuple[str, list[str]]] = {
    "financial_report": (
        "Financial Report",
        ["revenue", "operating expenses", "net income", "gross profit",
         "ebitda", "financial summary", "financial report"],
    ),
    "financial_statement": (
        "Financial Statement",
        ["balance sheet", "income statement", "statement of cash",
         "statement of operations"],
    ),
    "invoice": (
        "Invoice",
        ["invoice number", "bill to", "remit to", "amount due",
         "invoice date"],
    ),
    "budget": (
        "Budget",
        ["budget vs actual", "fiscal year budget", "budgeted amount"],
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
    "master_services_agreement": (
        "Master Services Agreement",
        ["master services agreement", "this msa"],
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
    "procurement": (
        "Procurement Document",
        ["request for proposal", "request for quote",
         "invitation for bid", "solicitation number"],
    ),
    "technical_specification": (
        "Technical Specification",
        ["technical specification", "performance specification",
         "shall comply with"],
    ),
    "contract": (
        "Contract",
        ["this agreement", "the parties", "effective date",
         "governing law", "whereas"],
    ),
}

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

SUGGESTED_PROMPTS: dict[str, str] = {
    family.key: family.suggested_prompt for family in HEADING_FAMILIES
}
SUGGESTED_PROMPTS.update(
    {
        "funding_table": (
            "Extract the funding table with allocations and amounts."
        ),
        "line_items": (
            "Extract all line items with descriptions, quantities, and prices."
        ),
    }
)

ORGANIZATION_PATTERN = re.compile(
    r"\b(?:[A-Z][A-Za-z&.,]*\s+){1,4}"
    r"(?:Inc\.?|LLC|L\.L\.C\.|Corp\.?|Corporation|"
    r"Company|Co\.|Ltd\.?|Industries|Group|Partners)\b"
)

KNOWN_TEMPLATE_KEYS = set(TABLE_FAMILIES) | {
    family.key for family in HEADING_FAMILIES
}


def _keyword_score(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug[:60] or "field"


def _humanize_table_label(page_number: int, headers: list[str]) -> str:
    if headers:
        first = headers[0].strip()
        if first and not first.lower().startswith("column"):
            return first[:80]
    return f"Table (page {page_number})"


def _is_budget_actual_table(headers: list[str]) -> bool:
    haystack = " ".join(headers).lower()
    return "budget" in haystack and "actual" in haystack


def _heading_matches(text: str) -> list[HeadingFamily]:
    return [family for family in HEADING_FAMILIES if family.pattern.search(text)]


def _label_from_headers(
    headers: list[str],
    surrounding_text: str,
    page_number: int,
    index: int,
) -> tuple[str, str, float, list[str]]:
    haystack = (
        " ".join(headers) + " " + surrounding_text[:400]
    ).lower()

    best_key: str | None = None
    best_label = _humanize_table_label(page_number, headers)
    best_score = 0

    for key, (label, keywords) in TABLE_FAMILIES.items():
        score = _keyword_score(haystack, keywords)
        if score > best_score:
            best_key = key
            best_label = label
            best_score = score

    heading_hits = _heading_matches(surrounding_text[:800])
    table_headings = [
        family for family in heading_hits
        if family.extraction_type == "table"
    ]

    if table_headings:
        family = table_headings[0]
        best_key = family.key
        best_label = family.label
        confidence = 0.98
        evidence = [f"Heading on page {page_number}: {family.label}"]
        if headers:
            evidence.append("Columns: " + ", ".join(headers[:8]))
        return best_key, best_label, confidence, evidence

    if _is_budget_actual_table(headers):
        lowered = surrounding_text.lower()
        if "operating expense" in lowered:
            best_key = "operating_expenses"
            best_label = "Operating Expenses"
        elif "revenue" in lowered:
            best_key = "revenue_analysis"
            best_label = "Revenue Analysis"
        else:
            best_key = "budget_vs_actual"
            best_label = "Budget vs Actual"
        confidence = 0.93
        evidence = [
            f"Budget/actual/variance columns on page {page_number}",
        ]
        return best_key, best_label, confidence, evidence

    if best_score < TABLE_MATCH_MIN_SCORE:
        best_key = f"table_p{page_number}_{index}"
        confidence = 0.72 if headers else 0.6
        evidence = [f"Unlabeled table on page {page_number}"]
        if headers:
            evidence.append("Columns: " + ", ".join(headers[:8]))
        return best_key, best_label, confidence, evidence

    confidence = min(0.99, 0.78 + 0.07 * best_score)
    evidence = [f"Matched {best_label} from table headers on page {page_number}"]
    return best_key or f"table_p{page_number}_{index}", best_label, confidence, evidence


def _merge_targets(targets: list[DetectedTarget]) -> list[DetectedTarget]:
    merged: dict[str, DetectedTarget] = {}

    for target in targets:
        existing = merged.get(target.key)
        if existing is None:
            merged[target.key] = target
            continue

        existing.pages = sorted(set(existing.pages + target.pages))
        existing.confidence = max(existing.confidence, target.confidence)
        existing.evidence = list(
            dict.fromkeys(existing.evidence + target.evidence)
        )
        if not existing.columns and target.columns:
            existing.columns = target.columns
        if not existing.suggested_prompt and target.suggested_prompt:
            existing.suggested_prompt = target.suggested_prompt

    return list(merged.values())


def _sort_targets(
    targets: list[DetectedTarget],
    document_family: str,
) -> list[DetectedTarget]:
    preferred = FAMILY_DEFAULT_KEYS.get(document_family, [])
    rank = {key: index for index, key in enumerate(preferred)}

    return sorted(
        targets,
        key=lambda target: (
            rank.get(target.key, len(preferred)),
            -target.confidence,
            min(target.pages) if target.pages else 999,
        ),
    )


def _classify_document_family(
    text: str,
) -> tuple[str, str, float]:
    lowered = text.lower()

    scores = {
        key: _keyword_score(lowered, keywords)
        for key, (_label, keywords) in DOCUMENT_FAMILIES.items()
    }

    ranked = sorted(
        scores.items(), key=lambda item: item[1], reverse=True
    )

    if not ranked or ranked[0][1] == 0:
        return "unknown", "Unknown / General Document", 0.3

    top_key, top_score = ranked[0]
    runner_up_score = ranked[1][1] if len(ranked) > 1 else 0

    if (
        top_score >= FAMILY_MIN_SCORE
        and top_score - runner_up_score >= FAMILY_SCORE_MARGIN
    ):
        label = DOCUMENT_FAMILIES[top_key][0]
        confidence = min(0.99, 0.72 + 0.06 * top_score)
        return top_key, label, round(confidence, 2)

    if top_score >= 1:
        return (
            "generic_business",
            "Generic Business Document",
            0.55,
        )

    return "unknown", "Unknown / General Document", 0.35


def _target(
    *,
    key: str,
    label: str,
    extraction_type: ExtractionType,
    pages: list[int],
    confidence: float,
    evidence: list[str],
    columns: list[str] | None = None,
) -> DetectedTarget:
    prompt = SUGGESTED_PROMPTS.get(key)
    if prompt is None:
        if extraction_type == "table":
            prompt = f"Extract the {label} table with all rows and columns."
        elif extraction_type == "field":
            prompt = f"Extract the {label}."
        else:
            prompt = f"Extract {label.lower()} from this document."

    return DetectedTarget(
        key=key,
        label=label,
        extraction_type=extraction_type,
        pages=sorted(set(pages)),
        confidence=round(confidence, 2),
        evidence=evidence,
        suggested_prompt=prompt,
        columns=columns or [],
    )


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

    detected: list[DetectedTarget] = []

    for page in scan_pages:
        page_text = page.final_text or ""
        raw_tables = page.tables_json or []

        for index, table in enumerate(raw_tables):
            headers = [
                str(header) for header in (table.get("headers") or [])
            ]
            key, label, confidence, evidence = _label_from_headers(
                headers=headers,
                surrounding_text=page_text,
                page_number=page.page_number,
                index=index,
            )
            detected.append(
                _target(
                    key=key,
                    label=label,
                    extraction_type="table",
                    pages=[page.page_number],
                    confidence=confidence,
                    evidence=evidence,
                    columns=headers,
                )
            )

        # Heading-based discovery even when pdfplumber missed the table.
        for family in _heading_matches(page_text):
            already = any(
                item.key == family.key and page.page_number in item.pages
                for item in detected
            )
            if already:
                continue

            columns: list[str] = []
            if raw_tables:
                columns = [
                    str(header)
                    for header in (raw_tables[0].get("headers") or [])
                ]

            detected.append(
                _target(
                    key=family.key,
                    label=family.label,
                    extraction_type=family.extraction_type,
                    pages=[page.page_number],
                    confidence=0.96,
                    evidence=[
                        f"Heading '{family.label}' on page {page.page_number}"
                    ],
                    columns=columns,
                )
            )

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
            detected.append(
                _target(
                    key=key,
                    label=label,
                    extraction_type="field",
                    pages=matching_pages,
                    confidence=0.86,
                    evidence=[
                        f"Labeled value '{label}' on pages "
                        + ", ".join(str(n) for n in matching_pages)
                    ],
                )
            )

    known_probe_labels = {probe_label.lower() for _, _, probe_label in FIELD_PROBES}

    for page in scan_pages:
        for pair in scan_page_for_labeled_pairs(page=page):
            if pair.normalized_label in known_probe_labels:
                continue

            detected.append(
                _target(
                    key=f"kv_{_slugify(pair.raw_label)}",
                    label=pair.raw_label,
                    extraction_type="field",
                    pages=[page.page_number],
                    confidence=pair.confidence,
                    evidence=[
                        f"'{pair.raw_label}: {pair.value}' on page "
                        f"{page.page_number} ({pair.method})"
                    ],
                )
            )

    entities = extract_generic_entities(combined_text)
    detected_contacts = entities["email"] + entities["phone"]

    if detected_contacts:
        contact_pages = [
            page.page_number
            for page in scan_pages
            if any(
                value in (page.final_text or "")
                for value in detected_contacts
            )
        ] or [scan_pages[0].page_number] if scan_pages else []

        detected.append(
            _target(
                key="contacts",
                label="Contacts",
                extraction_type="contact",
                pages=contact_pages,
                confidence=0.9,
                evidence=[
                    f"{len(detected_contacts)} email/phone values detected"
                ],
            )
        )

    family_key, family_label, family_confidence = _classify_document_family(
        combined_text
    )

    if family_key in {"unknown", "generic_business"} and combined_text.strip():
        try:
            classification = await classify_contract(
                pages=scan_pages,
                ai_provider=ai_provider,
            )
            mapped_key, mapped_label = _map_contract_type_to_family(
                classification.document_type,
                classification.confidence,
            )
            if mapped_key not in {"unknown", "generic_business"}:
                family_key = mapped_key
                family_label = mapped_label
                family_confidence = round(classification.confidence, 2)
        except AIProviderError:
            pass
        except Exception:
            pass

    detected = _merge_targets(detected)
    detected = _sort_targets(detected, family_key)

    primary = [
        target for target in detected
        if target.confidence >= PRIMARY_CONFIDENCE_MIN
    ]
    possible = [
        target for target in detected
        if target.confidence < PRIMARY_CONFIDENCE_MIN
    ]

    detected_tables = [
        DetectedTable(
            key=target.key,
            label=target.label,
            pages=target.pages,
            confidence=target.confidence,
            suggested_prompt=target.suggested_prompt,
            columns=target.columns,
        )
        for target in primary
        if target.extraction_type == "table"
    ]

    obligation_labels = [
        target.label
        for target in primary
        if target.extraction_type == "obligation"
    ]

    organizations = set(ORGANIZATION_PATTERN.findall(combined_text))
    raw_table_count = sum(len(page.tables_json or []) for page in scan_pages)

    content_stats = ContentStats(
        tables=max(raw_table_count, len(detected_tables)),
        dates=len(entities["date"]),
        currency_values=len(entities["money"]),
        organizations=len(organizations),
    )

    counts = DetectionCounts(
        fields=sum(
            1 for target in primary if target.extraction_type == "field"
        ),
        tables=sum(
            1 for target in primary if target.extraction_type == "table"
        ),
        contacts=sum(
            1 for target in primary if target.extraction_type == "contact"
        ),
        obligations=sum(
            1 for target in primary if target.extraction_type == "obligation"
        ),
        clauses=sum(
            1 for target in primary if target.extraction_type == "clause"
        ),
        signatures=sum(
            1 for target in primary if target.extraction_type == "signature"
        ),
    )

    return StructureDetectionResponse(
        document_id=document.id,
        document_family=family_key,
        document_family_label=family_label,
        document_family_confidence=family_confidence,
        detected_fields=detected_fields,
        detected_tables=detected_tables,
        detected_contacts=detected_contacts,
        detected_obligations=obligation_labels,
        detected_targets=primary,
        possible_targets=possible,
        content_stats=content_stats,
        counts=counts,
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
        "Master Services Agreement": "master_services_agreement",
    }

    contract_types = {
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
        return key, DOCUMENT_FAMILIES.get(key, (document_type, []))[0]

    if document_type in contract_types:
        return "contract", DOCUMENT_FAMILIES["contract"][0]

    return "unknown", "Unknown / General Document"
