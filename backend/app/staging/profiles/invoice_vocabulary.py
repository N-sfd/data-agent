"""invoice@1's controlled alias vocabulary.

Owned by the invoice profile, never by the universal source extractor: the
extractor reports "a label 'Invoice #' has value 'BOS-24-1187'"; this module
decides that label means invoice.invoice_number.

Matching is EXACT on a normalized label (see `normalize_label`), so similar
but different concepts ("Invoice Total", "Amount Due", "Taxable Amount") are
never merged by accident. A few deliberately generic labels ("Date",
"Total") are mapped but flagged `ambiguous`, which makes the staged value
Needs Review rather than silently trusted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PARENS = re.compile(r"\([^)]*\)")
_RATE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def normalize_label(label: str) -> str:
    """'Invoice #:' → 'invoice number'; 'P.O. No.' → 'po number';
    'Sales Tax (8.25%)' → 'sales tax'."""

    text = _PARENS.sub(" ", label or "").lower()
    text = _RATE.sub(" ", text)
    text = text.replace("#", " number ").replace("&", " and ")
    text = re.sub(r"\bp\.?\s?o\.?(?=\s|$)", "po", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\b(no|num|nbr)\b", "number", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bnumber number\b", "number", text)
    return text


def rate_in_label(label: str) -> str | None:
    match = _RATE.search(label or "")
    return f"{match.group(1)}%" if match else None


@dataclass(frozen=True)
class Alias:
    canonical: str
    ambiguous: bool = False
    note: str | None = None


def _aliases(canonical: str, *labels: str, ambiguous: bool = False, note: str | None = None) -> dict[str, Alias]:
    return {label: Alias(canonical, ambiguous, note) for label in labels}


# --- scalar fields --------------------------------------------------------------

SCALAR_ALIASES: dict[str, Alias] = {
    **_aliases("invoice.invoice_number", "invoice number", "inv number", "invoice id", "invoice ref", "invoice reference", "bill number", "tax invoice number"),
    **_aliases("invoice.invoice_date", "invoice date", "date of invoice", "inv date", "issue date", "date issued", "billing date", "invoice issue date", "date of issue"),
    **_aliases("invoice.invoice_date", "date", ambiguous=True, note="The label 'Date' is generic; confirm it is the invoice date."),
    **_aliases("invoice.due_date", "due date", "payment due", "payment due date", "date due", "pay by", "due by", "due on"),
    **_aliases("invoice.currency", "currency", "currency code", "invoice currency"),
    **_aliases("invoice.payment_terms", "terms", "payment terms", "terms of payment", "credit terms"),
    **_aliases("invoice.type", "document type", "invoice type"),
    **_aliases("invoice.supplier.name", "supplier", "vendor", "supplier name", "vendor name", "seller", "sold by", "from"),
    **_aliases("invoice.supplier.number", "supplier number", "supplier id", "supplier code", "vendor number", "vendor id", "vendor code"),
    **_aliases(
        "invoice.supplier.tax_id", "tax id", "federal tax id", "tax id number", "tax identification number", "ein", "fein",
        "tin", "vat number", "vat id", "vat reg number", "vat registration number", "gst number", "abn", "company tax id",
    ),
    **_aliases("invoice.supplier.remit_to", "remit to", "remit payment to", "remittance address", "pay to", "make checks payable to"),
    **_aliases("invoice.customer.name", "customer", "customer name", "client", "client name", "buyer"),
    **_aliases(
        "invoice.customer.number", "customer number", "customer id", "customer code", "customer account", "account number",
        "account", "account id", "client id", "acct number",
    ),
    **_aliases("invoice.customer.bill_to_address", "bill to", "billed to", "invoice to", "invoiced to", "bill to address", "billing address", "sold to"),
    **_aliases("invoice.customer.ship_to_address", "ship to", "shipped to", "deliver to", "delivered to", "delivery address", "ship to address", "shipping address"),
    **_aliases("invoice.reference.po_number", "po number", "purchase order", "purchase order number", "customer po", "customer po number", "your po", "po reference"),
    **_aliases("invoice.reference.contract_number", "contract number", "contract", "agreement number", "contract reference"),
    **_aliases("invoice.reference.receipt_number", "receipt number", "receiving number", "goods receipt", "goods receipt number", "grn", "gr number"),
    **_aliases("invoice.reference.order_number", "order number", "sales order", "sales order number", "so number", "your order number"),
    **_aliases("invoice.total.subtotal", "subtotal", "sub total", "merchandise total", "items total", "lines total"),
    **_aliases("invoice.total.invoice_amount", "invoice total", "total amount", "grand total", "invoice amount", "total invoice", "total invoice amount"),
    **_aliases("invoice.total.invoice_amount", "total", ambiguous=True, note="The label 'Total' alone may mean invoice total or amount due; confirm."),
    **_aliases("invoice.total.amount_paid", "amount paid", "paid", "payments", "payment received", "less payments", "deposit received", "payments received"),
    **_aliases("invoice.total.amount_due", "amount due", "balance due", "total due", "balance", "amount payable", "please pay", "due now", "total amount due"),
    **_aliases("invoice.total.tax", "total tax", "tax total", "total taxes"),
}

# Contact channels: assigned to supplier or customer by WHERE they appear
# (letterhead vs bill-to block) unless the label says whose they are.
CONTACT_LABELS = {
    "email": "email", "e mail": "email", "phone": "phone", "tel": "phone", "telephone": "phone",
    "phone number": "phone", "fax": "fax", "mobile": "phone",
}

# --- charges -----------------------------------------------------------------

# (charge type, label keywords) — first match wins, order matters
# ("shipping and handling" is freight before handling).
CHARGE_TYPES: list[tuple[str, tuple[str, ...]]] = [
    ("discount", ("discount", "rebate", "promotion", "promo")),
    ("freight", ("freight", "shipping", "carriage", "postage", "delivery charge")),
    ("handling", ("handling",)),
    ("surcharge", ("surcharge",)),
    ("tax", ("sales tax", "vat", "gst", "hst", "pst", "qst", "use tax", "tax")),
    ("other", ("other charges", "service charge", "fee", "fees", "miscellaneous", "misc charge", "environmental")),
]
# Labels that contain a charge keyword but are totals, not charges.
NOT_A_CHARGE = {"total tax", "tax total", "total taxes", "taxable amount", "tax id", "vat number", "vat id", "tax id number", "federal tax id", "vat reg number", "vat registration number"}


def charge_type(normalized: str) -> str | None:
    if normalized in NOT_A_CHARGE or normalized in SCALAR_ALIASES:
        return None
    for kind, keywords in CHARGE_TYPES:
        if any(re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in keywords):
            return kind
    return None


# --- line-table headers -------------------------------------------------------------

LINE_HEADER_ALIASES: dict[str, str] = {
    **{h: "line_number" for h in ("line", "ln", "line number", "number", "line item")},
    **{h: "item_number" for h in ("item", "item number", "item code", "part", "part number", "sku", "product code", "product", "catalog number", "material", "article", "item id")},
    **{h: "description" for h in ("description", "item description", "details", "service", "services", "product description", "particulars", "service description")},
    **{h: "quantity" for h in ("qty", "quantity", "qty shipped", "qty invoiced", "units", "hours", "days", "hrs")},
    **{h: "uom" for h in ("uom", "unit", "um", "u m", "unit of measure", "uofm")},
    **{h: "unit_price" for h in ("unit price", "price", "rate", "unit cost", "cost", "price each", "each", "unit rate")},
    **{h: "amount" for h in ("amount", "line total", "total", "extended", "extended price", "ext price", "extension", "line amount", "net amount", "value")},
    **{h: "tax" for h in ("tax", "vat", "gst", "tax amount")},
    **{h: "po_line" for h in ("po line", "po ln", "po line number", "po item")},
}
