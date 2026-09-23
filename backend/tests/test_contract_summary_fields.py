from app.services.contract_summary_fields import match_label, validate_value


def test_match_label_recognizes_sf33_numbered_labels() -> None:
    assert match_label("2. CONTRACT NUMBER") == "contract_number"
    assert match_label("3. SOLICITATION NUMBER") == "solicitation_number"
    assert match_label("5. DATE ISSUED") == "date_issued"
    assert match_label("28. AWARD DATE") == "award_date"
    assert match_label("6. REQUISITION/PURCHASE NUMBER") == "purchase_request_number"


def test_match_label_returns_none_for_unrecognized_text() -> None:
    assert match_label("10. FOR INFORMATION CALL") is None
    assert match_label("PART II - CONTRACT CLAUSES") is None


def test_more_specific_phrase_wins_over_shorter_contained_phrase() -> None:
    # "solicitation number" must not fall through to a generic "number"
    # bucket that doesn't exist, and must not be confused with "contract
    # number" despite sharing the word "number".
    assert match_label("3. SOLICITATION NUMBER") == "solicitation_number"
    assert match_label("2. CONTRACT NUMBER") == "contract_number"


def test_identifier_validator_accepts_contract_number_shape() -> None:
    result = validate_value("contract_number", "47QRCA25DSF07")
    assert result.is_valid


def test_identifier_validator_rejects_prose() -> None:
    result = validate_value(
        "solicitation_number", "whether or not Contractors shall submit labor pricing"
    )
    assert not result.is_valid


def test_date_validator_accepts_slash_date() -> None:
    assert validate_value("date_issued", "02/03/2025").is_valid


def test_date_validator_accepts_iso_date() -> None:
    assert validate_value("award_date", "2025-04-15").is_valid


def test_date_validator_rejects_identifier_shaped_value() -> None:
    # The confirmed regression: an identifier must not pass as a date.
    result = validate_value("date_issued", "47QRCA23R0001")
    assert not result.is_valid


def test_naics_validator_requires_six_digits() -> None:
    assert validate_value("naics", "541990").is_valid
    assert not validate_value("naics", "Codes").is_valid
    assert not validate_value("naics", "54199").is_valid


def test_ueid_validator_requires_twelve_alphanumeric() -> None:
    assert validate_value("ueid", "LLKXZRFEQMR3").is_valid
    assert not validate_value("ueid", "TOO-SHORT").is_valid


def test_email_validator() -> None:
    assert validate_value("email", "gabrina.daniels@gsa.gov").is_valid
    assert not validate_value("email", "not an email").is_valid


def test_phone_validator() -> None:
    assert validate_value("telephone", "541-1679").is_valid
    assert validate_value("telephone", "(240) 541-1679").is_valid
    assert not validate_value("telephone", "call me maybe").is_valid


def test_name_validator_rejects_heading_like_text() -> None:
    assert validate_value("contracting_officer_name", "Esther Shannon").is_valid
    assert not validate_value(
        "contracting_officer_name", "PART IV - REPRESENTATIONS AND INSTRUCTIONS"
    ).is_valid


def test_amount_validator() -> None:
    assert validate_value("amount", "$2,500.00").is_valid
    assert validate_value("amount", "600000000").is_valid
    assert not validate_value("amount", "Codes").is_valid


def test_unrecognized_field_key_has_no_validator_and_passes() -> None:
    result = validate_value("some_unmapped_field", "anything at all")
    assert result.is_valid
    assert result.reason == "no_validator_defined_for_field"
