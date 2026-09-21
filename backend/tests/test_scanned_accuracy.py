"""Regression tests for Scanned Document Accuracy & Cleanup.

Government-contract style SF-33 geometry: layout association, label
rejection, consensus without inventing IDs, confidence component split,
and targeted OCR retry hooks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.candidate_consensus import ExtractionCandidate, resolve_candidates
from app.services.confidence_engine import explain_confidence
from app.services.label_rejection import (
    looks_like_form_label,
    looks_like_identifier_sentence,
    reject_as_field_value,
)
from app.services.ocr_word_layer import OcrLayout, OcrLine, OcrWord
from app.services.result_validation import build_validation_result
from app.services.scanned_accuracy import layout_from_json
from app.services.scanned_form_layout import (
    associate_label_value,
    reconstruct_table_from_lines,
)
from app.services.targeted_ocr import TargetedOcrResult, crop_and_ocr


def _word(
    text: str,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    conf: float = 0.95,
    block: int = 0,
    line: int = 0,
    word: int = 0,
) -> OcrWord:
    return OcrWord(
        text=text,
        conf=conf,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        block_num=block,
        line_num=line,
        word_num=word,
    )


def _line(words: list[OcrWord], *, block: int = 0, line: int = 0) -> OcrLine:
    confs = [item.conf for item in words]
    return OcrLine(
        text=" ".join(item.text for item in words),
        conf=sum(confs) / len(confs) if confs else 0.0,
        x0=min(item.x0 for item in words),
        y0=min(item.y0 for item in words),
        x1=max(item.x1 for item in words),
        y1=max(item.y1 for item in words),
        words=words,
    )


def _gov_contract_layout() -> OcrLayout:
    """Synthetic SF-33 header geometry for solicitation + contract fields."""

    sol_label = _line(
        [
            _word("3.", x0=40, y0=80, x1=55, y1=95, word=0, line=0),
            _word("SOLICITATION", x0=58, y0=80, x1=160, y1=95, word=1, line=0),
            _word("NUMBER", x0=163, y0=80, x1=230, y1=95, word=2, line=0),
        ],
        line=0,
    )
    type_label = _line(
        [
            _word("4.", x0=280, y0=80, x1=295, y1=95, word=0, line=1),
            _word("TYPE", x0=298, y0=80, x1=340, y1=95, word=1, line=1),
            _word("OF", x0=343, y0=80, x1=365, y1=95, word=2, line=1),
            _word("SOLICITATION", x0=368, y0=80, x1=470, y1=95, word=3, line=1),
        ],
        line=1,
    )
    sol_value = _line(
        [_word("47QRCA25DSF07", x0=58, y0=100, x1=200, y1=118, conf=0.96, line=2)],
        line=2,
    )
    type_value = _line(
        [_word("RFQ", x0=298, y0=100, x1=340, y1=118, conf=0.93, line=3)],
        line=3,
    )
    date_label = _line(
        [
            _word("5.", x0=40, y0=140, x1=55, y1=155, line=4),
            _word("DATE", x0=58, y0=140, x1=100, y1=155, line=4),
            _word("ISSUED", x0=103, y0=140, x1=165, y1=155, line=4),
        ],
        line=4,
    )
    date_value = _line(
        [_word("03/15/2025", x0=58, y0=160, x1=150, y1=175, conf=0.94, line=5)],
        line=5,
    )
    issued_label = _line(
        [
            _word("7.", x0=40, y0=200, x1=55, y1=215, line=6),
            _word("ISSUED", x0=58, y0=200, x1=110, y1=215, line=6),
            _word("BY", x0=113, y0=200, x1=140, y1=215, line=6),
        ],
        line=6,
    )
    issued_value = _line(
        [
            _word("GSA", x0=58, y0=220, x1=95, y1=235, conf=0.97, line=7),
            _word("FAS", x0=98, y0=220, x1=130, y1=235, conf=0.97, line=7),
        ],
        line=7,
    )
    lines = [
        sol_label,
        type_label,
        sol_value,
        type_value,
        date_label,
        date_value,
        issued_label,
        issued_value,
    ]
    words = [word for line in lines for word in line.words]
    return OcrLayout(
        words=words,
        lines=lines,
        mean_word_confidence=0.95,
    )


def test_label_rejection_blocks_form_labels_as_values() -> None:
    assert looks_like_form_label("3. SOLICITATION NUMBER")
    assert looks_like_form_label("A. NAME")
    assert looks_like_form_label("6. REQUISITION/PURCHASE NUMBER")
    assert reject_as_field_value(
        "3. SOLICITATION NUMBER", value_type="identifier"
    )
    assert reject_as_field_value(
        "47QRCA25DSF07 4. TYPE OF SOLICITATION",
        value_type="contract_number",
    )
    assert looks_like_identifier_sentence(
        "3. SOLICITATION NUMBER 4. TYPE OF SOLICITATION"
    )
    assert reject_as_field_value("47QRCA25DSF07", value_type="identifier") is None


def test_observed_production_label_mashups_never_become_values() -> None:
    """Regression: exact bad scalars seen on the scanned GSA contract."""

    bad_cases = [
        (
            "solicitation_number",
            "A. NAME / B. TELEPHONE / C. E-MAIL ADDRESS",
        ),
        (
            "type_of_solicitation",
            "5. DATE ISSUED / 6. REQUISITION/PURCHASE NUMBER",
        ),
        (
            "contract_number",
            "3. SOLICITATION NUMBER / 4. TYPE OF SOLICITATION",
        ),
        (
            "contract_no",
            "47QRCA25DSF07, Current as of Modification BASE",
        ),
        ("effective_date", "of any change to the CAF"),
        ("date_issued", "6. REQUISITION/PURCHASE NUMBER"),
        (
            "issued_by",
            "CODE 47QRCA / 8. ADDRESS OFFER TO (If other than Item 7)",
        ),
    ]
    for field_key, value in bad_cases:
        reason = reject_as_field_value(value, field_key=field_key)
        assert reason, f"{field_key} unexpectedly accepted: {value!r}"

    # Plausible clean values must still pass.
    assert (
        reject_as_field_value("4/15/2025", field_key="date", value_type="date")
        is None
    )
    assert (
        reject_as_field_value(
            "47QRCA25DSF07", field_key="solicitation_number", value_type="identifier"
        )
        is None
    )


def test_layout_associates_solicitation_number_not_neighbor_label() -> None:
    layout = _gov_contract_layout()
    hit = associate_label_value(
        layout,
        requested_label="Solicitation Number",
        value_type="solicitation_number",
    )
    assert hit is not None
    assert hit.value == "47QRCA25DSF07"
    assert hit.method.startswith("layout_form_cell")
    assert hit.bbox[0] >= 50


def test_layout_extracts_date_issued_and_issued_by() -> None:
    layout = _gov_contract_layout()
    date_hit = associate_label_value(
        layout, requested_label="Date Issued", value_type="date"
    )
    issued_hit = associate_label_value(
        layout, requested_label="Issued By", value_type="text"
    )
    assert date_hit is not None
    assert date_hit.value == "03/15/2025"
    assert issued_hit is not None
    assert "GSA" in issued_hit.value


def test_conflicting_ocr_candidates_need_review_not_guess() -> None:
    result = resolve_candidates(
        [
            ExtractionCandidate(
                value="47QRCA25DSF07",
                raw_ocr="47QRCA25DSF07",
                method="layout_form_cell_below",
                ocr_confidence=0.96,
                layout_confidence=0.9,
                source_page=1,
            ),
            ExtractionCandidate(
                value="47QRCA2SDSF07",
                raw_ocr="47QRCA2SDSF07",
                method="targeted_crop_ocr",
                ocr_confidence=0.91,
                layout_confidence=0.75,
                source_page=1,
            ),
        ],
        value_type="contract_number",
    )
    assert result.decision == "needs_review"
    assert result.reason == "conflicting_candidates"
    assert result.selected is None
    assert result.normalized_value is None


def test_unanimous_high_confidence_auto_selects() -> None:
    result = resolve_candidates(
        [
            ExtractionCandidate(
                value="47QRCA25DSF07",
                raw_ocr="47QRCA25DSF07",
                method="layout_form_cell_below",
                ocr_confidence=0.96,
                layout_confidence=0.9,
                source_page=2,
                source_bbox=[120, 82, 275, 108],
            ),
            ExtractionCandidate(
                value="47QRCA25DSF07",
                raw_ocr="47QRCA25DSF07",
                method="targeted_crop_ocr",
                ocr_confidence=0.94,
                layout_confidence=0.8,
                source_page=2,
            ),
        ],
        value_type="contract_number",
    )
    assert result.decision == "auto_select"
    assert result.normalized_value == "47QRCA25DSF07"
    evidence = result.evidence_payload(field_key="contract_number")
    assert evidence["raw_ocr"] == "47QRCA25DSF07"
    assert evidence["source_page"] == 2
    assert evidence["source_bbox"] == [120, 82, 275, 108]
    assert evidence["extraction_method"] == "layout_form_cell_below"


def test_validation_rejects_form_label_even_with_source_presence() -> None:
    result = build_validation_result(
        value="3. SOLICITATION NUMBER",
        value_type="identifier",
        source_text="3. SOLICITATION NUMBER",
        page_text="3. SOLICITATION NUMBER 47QRCA25DSF07",
    )
    assert result.status == "failed"
    assert any(
        check.type == "label_rejection" and check.status == "failed"
        for check in result.checks
    )


def test_validation_failed_caps_final_confidence_below_medium() -> None:
    page = MagicMock(requires_ocr=True, ocr_succeeded=True, text_coverage_ratio=0.9)
    explained = explain_confidence(
        method="layout_form_cell_below",
        page=page,
        source_grounded=True,
        validation_passed=False,
        ocr_confidence=0.99,
        layout_confidence=0.95,
        exact_label_match=True,
    )
    assert explained.components is not None
    assert explained.components.ocr == 0.99
    assert explained.components.validation == 0.0
    assert explained.components.final <= 0.59
    assert explained.score <= 0.59
    assert explained.band == "low"


def test_table_reconstruction_from_coordinates_not_flattened() -> None:
    header = _line(
        [
            _word("CLIN", x0=40, y0=40, x1=80, y1=55, line=0, word=0),
            _word("DESCRIPTION", x0=120, y0=40, x1=220, y1=55, line=0, word=1),
            _word("AMOUNT", x0=280, y0=40, x1=340, y1=55, line=0, word=2),
        ],
        line=0,
    )
    row1 = _line(
        [
            _word("0001", x0=40, y0=60, x1=80, y1=75, line=1, word=0),
            _word("Support", x0=120, y0=60, x1=190, y1=75, line=1, word=1),
            _word("$100.00", x0=280, y0=60, x1=340, y1=75, line=1, word=2),
        ],
        line=1,
    )
    row2 = _line(
        [
            _word("0002", x0=40, y0=80, x1=80, y1=95, line=2, word=0),
            _word("Travel", x0=120, y0=80, x1=175, y1=95, line=2, word=1),
            _word("$50.00", x0=280, y0=80, x1=330, y1=95, line=2, word=2),
        ],
        line=2,
    )
    layout = OcrLayout(
        words=[w for line in (header, row1, row2) for w in line.words],
        lines=[header, row1, row2],
        mean_word_confidence=0.9,
    )
    table = reconstruct_table_from_lines(layout)
    assert table is not None
    assert table["source"] == "ocr_layout_coordinates"
    assert table["column_count"] >= 2
    assert len(table["rows"]) == 2
    assert isinstance(table["rows"][0], dict)
    joined = " ".join(str(v) for row in table["rows"] for v in row.values())
    assert "0001" in joined and "0002" in joined


def test_layout_round_trip_json_preserves_words() -> None:
    layout = _gov_contract_layout()
    restored = layout_from_json(layout.to_json())
    assert restored is not None
    assert len(restored.words) == len(layout.words)
    assert any("47QRCA25DSF07" in line.text for line in restored.lines)


def test_targeted_ocr_crops_region_not_full_page() -> None:
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    page_bytes = buffer.getvalue()

    with patch(
        "app.services.targeted_ocr.ocr_image_bytes",
        return_value="47QRCA25DSF07",
    ) as ocr_mock:
        result = crop_and_ocr(
            page_bytes,
            bbox=(100.0, 80.0, 250.0, 120.0),
            page_width=612.0,
            page_height=792.0,
            target_min_edge_px=400,
        )
    assert isinstance(result, TargetedOcrResult)
    assert result.text == "47QRCA25DSF07"
    assert result.method == "targeted_crop_ocr"
    assert ocr_mock.call_count == 1
    called_bytes = ocr_mock.call_args[0][0]
    assert len(called_bytes) < len(page_bytes) * 2


def test_reject_label_candidates_in_consensus() -> None:
    result = resolve_candidates(
        [
            ExtractionCandidate(
                value="3. SOLICITATION NUMBER",
                raw_ocr="3. SOLICITATION NUMBER",
                method="label_value",
                ocr_confidence=0.99,
                layout_confidence=0.95,
            ),
            ExtractionCandidate(
                value="47QRCA25DSF07",
                raw_ocr="47QRCA25DSF07",
                method="layout_form_cell_below",
                ocr_confidence=0.96,
                layout_confidence=0.9,
            ),
        ],
        value_type="solicitation_number",
        field_key="solicitation_number",
    )
    assert result.decision == "auto_select"
    assert result.normalized_value == "47QRCA25DSF07"


def test_consensus_rejects_only_label_candidates_as_needs_review() -> None:
    result = resolve_candidates(
        [
            ExtractionCandidate(
                value="A. NAME / B. TELEPHONE / C. E-MAIL ADDRESS",
                raw_ocr="A. NAME / B. TELEPHONE / C. E-MAIL ADDRESS",
                method="label_value",
                ocr_confidence=0.99,
                layout_confidence=0.99,
            ),
        ],
        field_key="solicitation_number",
    )
    assert result.decision == "reject"
    assert result.selected is None
    assert result.review_status == "needs_review"


def test_kv_scanner_drops_label_as_value_pairs() -> None:
    from app.services.generic_kv_scanner import _scan_inline_regex

    text = (
        "SOLICITATION NUMBER     A. NAME / B. TELEPHONE\n"
        "TYPE OF SOLICITATION     5. DATE ISSUED\n"
        "CONTRACT NO.     47QRCA25DSF07\n"
    )
    pairs = _scan_inline_regex(text)
    values = {pair.value for pair in pairs}
    assert "A. NAME / B. TELEPHONE" not in values
    assert "5. DATE ISSUED" not in values
    assert "47QRCA25DSF07" in values
