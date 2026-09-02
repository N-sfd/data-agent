"""One-time seed for baseline, document-type-tagged extraction models.

Run manually once against the dev/prod database:

    cd backend
    ./.venv/Scripts/python.exe scripts/seed_extraction_models.py

Safe to re-run: skips any model whose name already exists.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.models.extraction_model import (  # noqa: E402
    ExtractionField,
    ExtractionModel,
)

MODELS: list[dict] = [
    {
        "name": "Contract Extraction",
        "description": "Contract summary, parties, dates, obligations, "
        "payment terms, and clauses.",
        "document_types": [
            "contract",
            "supplier_agreement",
            "master_services_agreement",
            "sow",
            "amendment",
            "government_contract",
        ],
        "fields": [
            ("Contract Summary", "text"),
            ("Parties", "text"),
            ("Dates", "date"),
            ("Obligations", "text"),
            ("Payment Terms", "text"),
            ("Clauses", "text"),
        ],
    },
    {
        "name": "Financial Report Extraction",
        "description": "Revenue, expenses, budget variance, and "
        "accounts payable.",
        "document_types": [
            "financial_report",
            "financial_statement",
            "budget",
            "statement",
        ],
        "fields": [
            ("Financial Summary", "text"),
            ("Revenue Analysis", "currency"),
            ("Operating Expenses", "currency"),
            ("Budget vs Actual", "text"),
            ("Accounts Payable", "currency"),
        ],
    },
    {
        "name": "Laboratory Report Extraction",
        "description": "Patient/report information, CBC, and iron "
        "studies results.",
        "document_types": ["laboratory_report"],
        "fields": [
            ("Patient & Report Info", "text"),
            ("CBC Results", "text"),
            ("Iron Studies", "text"),
            ("Abnormal Results", "text"),
            ("Reference Ranges", "text"),
        ],
    },
    {
        "name": "Business Requirements Extraction",
        "description": "Objectives, scope, requirements, KPIs, and "
        "risks from a BRD.",
        "document_types": ["business_requirements"],
        "fields": [
            ("Executive Summary", "text"),
            ("Objectives", "text"),
            ("Scope", "text"),
            ("Business Requirements", "text"),
            ("Functional Requirements", "text"),
            ("KPIs", "text"),
            ("Risks", "text"),
        ],
    },
    {
        "name": "Research / Idea Extraction",
        "description": "Market opportunity, competitors, feasibility, "
        "and monetization from a research/idea document.",
        "document_types": ["research_idea"],
        "fields": [
            ("Idea Overview", "text"),
            ("Market Opportunity", "text"),
            ("Target Audience", "text"),
            ("Competitors", "text"),
            ("Feasibility", "text"),
            ("Monetization", "text"),
            ("Risks", "text"),
        ],
    },
    {
        "name": "Invoice Extraction",
        "description": "Invoice header, supplier, line items, tax, "
        "and totals.",
        "document_types": ["invoice", "purchase_order"],
        "fields": [
            ("Invoice Header", "text"),
            ("Supplier", "text"),
            ("PO Number", "text"),
            ("Invoice Lines", "text"),
            ("Tax", "currency"),
            ("Totals", "currency"),
            ("Payment Terms", "text"),
        ],
    },
    {
        "name": "Solicitation Extraction",
        "description": "Government solicitation and procurement "
        "identifiers.",
        "document_types": ["government_contract", "procurement"],
        "fields": [
            ("Solicitation No.", "text"),
            ("Type", "text"),
            ("Date Issued", "date"),
            ("Contract No.", "text"),
            ("Requisition No.", "text"),
            ("Agency", "text"),
            ("Dates", "date"),
            ("CLINs", "text"),
        ],
    },
    {
        "name": "General / Custom Extraction",
        "description": "Discovered fields and tables for any "
        "document type.",
        "document_types": ["*"],
        "fields": [
            ("Discovered Fields", "text"),
            ("Discovered Tables", "text"),
            ("Document Summary", "text"),
        ],
    },
]


def main() -> None:
    database = SessionLocal()

    try:
        existing_names = set(
            database.scalars(select(ExtractionModel.name))
        )

        created = 0

        for spec in MODELS:
            if spec["name"] in existing_names:
                print(f"skip (exists): {spec['name']}")
                continue

            model = ExtractionModel(
                name=spec["name"],
                description=spec["description"],
                document_types=spec["document_types"],
            )
            database.add(model)
            database.flush()

            for field_name, data_type in spec["fields"]:
                database.add(
                    ExtractionField(
                        model_id=model.id,
                        field_name=field_name,
                        data_type=data_type,
                    )
                )

            created += 1
            print(f"created: {spec['name']}")

        database.commit()
        print(f"done — {created} model(s) created")
    finally:
        database.close()


if __name__ == "__main__":
    main()
