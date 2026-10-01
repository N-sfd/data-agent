from uuid import uuid4

import pytest

from app.database.session import SessionLocal
from app.models.document import Document
from app.staging import resolver

AWARD_LETTER = """Oct 02, 2023

William Martz
General Manager
Chugach Consolidated Solutions, LLC. (CCSL)

Janeen M. Bais
Contract Specialist, NAVFAC Marianas
Email: janeen.m.bais.civ@us.navy.mil

Subject: Award Acknowledgement CONTRACTS N40192-23-D-2803, SMALL BUSINESS
DESIGN-BUILD MULTIPLE AWARD CONSTRUCTION CONTRACT (SB-DBMACC)

A. SB-DBMACC contract number; N40192-23-D-2803
C. Cage Code and Unique Entity Identifier (UEI) number in the System for Award
Management (SAM); CAGE: 6XZF0  UEI: HME6LMM16LA1
F. Persons authorized to sign. Only signatures of those listed will be accepted by
Contracting Officers when awarding task orders; solicitation responses to FAR clauses.

Respectfully

William ( Bill )Martz
General Manager.
"""


@pytest.fixture
def database():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _resolve(database, monkeypatch, text: str, *, pages: int = 2, contract_structure: bool = False):
    monkeypatch.setattr(resolver, "_page_text", lambda db, document_id: text)
    monkeypatch.setattr(resolver, "_has_contract_structure", lambda db, document_id: contract_structure)
    document = Document(id=str(uuid4()), original_filename="award response.pdf", page_count=pages)
    return resolver.resolve_profile(database, document)


def test_letter_about_a_contract_resolves_as_correspondence(database, monkeypatch):
    resolution = _resolve(database, monkeypatch, AWARD_LETTER)
    assert resolution.family == "correspondence"
    assert resolution.family_label == "Correspondence"
    assert resolution.profile.profile_id == "generic_business_document"
    assert resolution.confident
    assert any("subject line" in reason and "closing" in reason for reason in resolution.reasons)


def test_letter_with_contract_structure_stays_a_contract(database, monkeypatch):
    resolution = _resolve(database, monkeypatch, AWARD_LETTER, contract_structure=True)
    assert resolution.family != "correspondence"


def test_long_document_is_never_treated_as_a_letter(database, monkeypatch):
    resolution = _resolve(database, monkeypatch, AWARD_LETTER, pages=40)
    assert resolution.family != "correspondence"


def test_one_letter_signal_is_not_enough(database, monkeypatch):
    text = AWARD_LETTER.replace("Respectfully", "")
    resolution = _resolve(database, monkeypatch, text)
    assert resolution.family != "correspondence"


def test_invoice_with_a_cover_note_keeps_the_invoice_profile(database, monkeypatch):
    invoice = (
        "Subject: Invoice for services\nDear Accounts Payable,\n"
        "Invoice Number: INV-1042\nInvoice Date: Sep 28, 2024\nBill To: Jordan Miller\n"
        "Remit To: Green Leaf\nAmount Due: $770.00\nSincerely,\nGreen Leaf"
    )
    resolution = _resolve(database, monkeypatch, invoice)
    assert resolution.family == "invoice"
