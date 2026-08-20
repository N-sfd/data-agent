from dataclasses import dataclass


@dataclass(frozen=True)
class StructuredColumnSpec:
    key: str
    label: str
    data_type: str  # "text" | "number" | "date" | "code"


@dataclass(frozen=True)
class StructuredTableSpec:
    family: str
    label: str
    description: str
    columns: list[StructuredColumnSpec]


STRUCTURED_TABLE_SPECS: list[StructuredTableSpec] = [
    StructuredTableSpec(
        family="line_item",
        label="Line Items / Schedule of Prices",
        description=(
            "Repeating CLIN/item rows such as a Schedule of Prices or an "
            "IDIQ Line Items table. Use is_maximum=true for IDIQ-style "
            "'Max Qty' / 'Max Amount' rows, false for awarded schedule rows."
        ),
        columns=[
            StructuredColumnSpec("clin", "CLIN / Item No.", "text"),
            StructuredColumnSpec("description", "Item / Supplies / Services", "text"),
            StructuredColumnSpec("quantity", "Quantity", "number"),
            StructuredColumnSpec("unit", "Unit", "text"),
            StructuredColumnSpec("unit_price", "Unit Price", "number"),
            StructuredColumnSpec("amount", "Amount", "number"),
            StructuredColumnSpec("is_maximum", "Is Maximum (true/false)", "text"),
            StructuredColumnSpec("period_label", "Period", "text"),
        ],
    ),
    StructuredTableSpec(
        family="performance_period",
        label="Performance Periods",
        description="Base period and option year rows (period, start, end, amount).",
        columns=[
            StructuredColumnSpec("period_label", "Period", "text"),
            StructuredColumnSpec("start_date", "Start Date", "date"),
            StructuredColumnSpec("end_date", "End Date", "date"),
            StructuredColumnSpec("amount", "Amount", "number"),
        ],
    ),
    StructuredTableSpec(
        family="delivery_schedule",
        label="Delivery Schedule",
        description="CLIN-level delivery rows with dates, quantities, and ship-to detail.",
        columns=[
            StructuredColumnSpec("clin", "CLIN", "text"),
            StructuredColumnSpec("delivery_date", "Delivery Date", "date"),
            StructuredColumnSpec("quantity", "Quantity", "number"),
            StructuredColumnSpec("ship_to_address", "Ship To Address", "text"),
            StructuredColumnSpec("dodaac", "DODAAC", "code"),
            StructuredColumnSpec("cage_code", "CAGE Code", "code"),
        ],
    ),
    StructuredTableSpec(
        family="key_position",
        label="Key Positions",
        description="Named key personnel positions with PIR/code and monthly amount.",
        columns=[
            StructuredColumnSpec("position_title", "Position", "text"),
            StructuredColumnSpec("pir", "PIR", "code"),
            StructuredColumnSpec("code", "Code", "code"),
            StructuredColumnSpec("monthly_amount", "Monthly Amount", "number"),
            StructuredColumnSpec("pws_section", "PWS Section", "text"),
            StructuredColumnSpec("wawf_field", "WAWF Field Name", "text"),
            StructuredColumnSpec("wawf_value", "WAWF Value", "text"),
        ],
    ),
    StructuredTableSpec(
        family="funding_line",
        label="Funding / ACRN",
        description="Accounting Classification Reference Number funding lines.",
        columns=[
            StructuredColumnSpec("acrn", "ACRN", "code"),
            StructuredColumnSpec("line_of_accounting", "Line of Accounting", "text"),
            StructuredColumnSpec("amount", "Amount", "number"),
        ],
    ),
    StructuredTableSpec(
        family="clause_reference",
        label="FAR / DFARS Clauses",
        description=(
            "FAR and DFARS clause citations. clause_family must be exactly "
            "'FAR' or 'DFARS'. Leave full_text empty unless the clause is "
            "incorporated by full text (not merely cited by reference)."
        ),
        columns=[
            StructuredColumnSpec("clause_family", "Clause Family (FAR or DFARS)", "text"),
            StructuredColumnSpec("clause_number", "Clause Number", "code"),
            StructuredColumnSpec("title", "Title", "text"),
            StructuredColumnSpec("effective_date", "Effective Date", "date"),
            StructuredColumnSpec("alternate", "Alternate (DFARS only)", "text"),
            StructuredColumnSpec("deviation", "Deviation (DFARS only)", "text"),
            StructuredColumnSpec(
                "variation_effective_date", "Variation Effective Date (DFARS only)", "date"
            ),
            StructuredColumnSpec("full_text", "Full Text (only if incorporated in full)", "text"),
        ],
    ),
    StructuredTableSpec(
        family="wawf_instruction",
        label="WAWF Instructions",
        description="Two-column Wide Area WorkFlow field-name/value instruction rows.",
        columns=[
            StructuredColumnSpec("field_name", "Field Name in WAWF", "text"),
            StructuredColumnSpec("instruction_value", "Data to be Entered in WAWF", "text"),
        ],
    ),
    StructuredTableSpec(
        family="insurance_requirement",
        label="Insurance Requirements",
        description="Required insurance coverage types and minimum amounts.",
        columns=[
            StructuredColumnSpec("coverage_type", "Coverage", "text"),
            StructuredColumnSpec("minimum_amount", "Minimum Required", "number"),
        ],
    ),
    StructuredTableSpec(
        family="order_range",
        label="Order Range",
        description="NAICS-based minimum/maximum order range rows.",
        columns=[
            StructuredColumnSpec("naics_code", "NAICS", "code"),
            StructuredColumnSpec("minimum_amount", "Minimum", "number"),
            StructuredColumnSpec("maximum_amount", "Maximum", "number"),
            StructuredColumnSpec("description", "Description", "text"),
        ],
    ),
    StructuredTableSpec(
        family="amendment_history",
        label="Amendment History",
        description=(
            "This contract's own internal amendment/modification history "
            "(e.g. an SF30 continuation table) — NOT a relationship to a "
            "different uploaded document."
        ),
        columns=[
            StructuredColumnSpec("amendment_number", "Amendment No.", "text"),
            StructuredColumnSpec("effective_date", "Effective Date", "date"),
            StructuredColumnSpec("description", "Description", "text"),
        ],
    ),
    StructuredTableSpec(
        family="contact",
        label="Contacts",
        description="Named contacts (e.g. Contracting Officer, Program Manager) with phone/email.",
        columns=[
            StructuredColumnSpec("contact_name", "Name", "text"),
            StructuredColumnSpec("role_title", "Role / Title", "text"),
            StructuredColumnSpec("phone_area_code", "Area Code", "code"),
            StructuredColumnSpec("phone_number", "Phone Number", "code"),
            StructuredColumnSpec("phone_extension", "Extension", "code"),
            StructuredColumnSpec("email", "Email", "text"),
        ],
    ),
    StructuredTableSpec(
        family="address",
        label="Addresses",
        description=(
            "Offeror, remittance, ship-to, and invoice-destination "
            "addresses. address_type must be one of: offeror, remittance, "
            "ship_to, invoice_destination, other."
        ),
        columns=[
            StructuredColumnSpec("address_type", "Address Type", "text"),
            StructuredColumnSpec("organization_name", "Organization", "text"),
            StructuredColumnSpec("street", "Street", "text"),
            StructuredColumnSpec("city", "City", "text"),
            StructuredColumnSpec("state", "State", "text"),
            StructuredColumnSpec("zip_code", "ZIP Code", "code"),
        ],
    ),
]
