from app.models.document import Document

SUPPORTING_DOCUMENT_TYPES = frozenset(
    {"Statement of Work", "Change Order", "Subcontract", "Purchase Order"}
)

RELATIONSHIP_TYPE_TO_STATUS: dict[str, str] = {
    "amendment_of": "Amendment",
    "change_order_of": "Supporting Document",
    "sow_of": "Supporting Document",
    "subcontract_of": "Supporting Document",
}


def compute_document_status_label(
    document: Document, contract_title: str | None = None
) -> str:
    """
    Derived (not AI-classified) from document_type and the confirmed
    parent relationship — one of "Original" | "Amendment" |
    "Renewal" | "Supporting Document" | "Unknown".
    """

    if not document.document_type:
        return "Unknown"

    if document.document_type == "Amendment":
        return "Amendment"

    if document.document_type in SUPPORTING_DOCUMENT_TYPES:
        return "Supporting Document"

    if (
        document.parent_document_id
        and document.parent_relationship_status == "confirmed"
        and document.parent_relationship_type
    ):
        return RELATIONSHIP_TYPE_TO_STATUS.get(
            document.parent_relationship_type, "Supporting Document"
        )

    if contract_title and "renewal" in contract_title.lower():
        return "Renewal"

    if document.document_type == "Other":
        return "Unknown"

    return "Original"
