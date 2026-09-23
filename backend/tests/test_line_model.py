from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from app.services.line_model import (
    best_available_lines,
    lines_from_blocks_fallback,
    lines_from_fitz_page,
    lines_from_ocr_layout,
)

REGRESSION_PDF_PATH = (
    Path(__file__).resolve().parents[2]
    / "reference"
    / "regression"
    / "Contract_47QRCA25DSF07 (2).pdf"
)
REGRESSION_PDF = str(REGRESSION_PDF_PATH)

# The regression contract is real customer-provided ground-truth data, kept
# out of git (large binary, not source code) - present locally for this
# session's validation but not on a fresh clone or in CI. Skip rather than
# fail so the suite stays green everywhere; these cases are also covered
# by synthetic fixtures below for machines without the file.
requires_regression_pdf = pytest.mark.skipif(
    not REGRESSION_PDF_PATH.exists(),
    reason="reference/regression contract not present on this machine (not committed to git)",
)


def _block(text: str, x0: float, y0: float, x1: float, y1: float) -> SimpleNamespace:
    return SimpleNamespace(text=text, x0=x0, y0=y0, x1=x1, y1=y1, extraction_method="native")


@requires_regression_pdf
def test_native_dict_mode_splits_merged_multi_label_block_into_separate_lines() -> None:
    # The confirmed Step 1 root cause: SF33 page 2 merges "2. CONTRACT
    # NUMBER", "3. SOLICITATION NUMBER" into block-mode text sharing one
    # bbox. Dict mode must recover them as distinct, correctly-positioned
    # lines.
    doc = fitz.open(REGRESSION_PDF)
    page = doc[1]  # page 2
    lines = lines_from_fitz_page(page=page, page_number=2)

    contract_label = next(l for l in lines if l.text.startswith("2. CONTRACT NUMBER"))
    solicitation_label = next(l for l in lines if l.text.startswith("3. SOLICITATION NUMBER"))

    assert contract_label.x0 != solicitation_label.x0
    assert abs(contract_label.x0 - 19.0) < 1.0
    assert abs(solicitation_label.x0 - 202.0) < 1.0


@requires_regression_pdf
def test_native_dict_mode_recovers_correct_label_value_column_alignment() -> None:
    doc = fitz.open(REGRESSION_PDF)
    page = doc[1]
    lines = lines_from_fitz_page(page=page, page_number=2)

    solicitation_label = next(l for l in lines if l.text.startswith("3. SOLICITATION NUMBER"))
    solicitation_value = next(l for l in lines if l.text == "47QRCA23R0001")

    # Same column (x aligned), value directly below the label (y increases).
    assert abs(solicitation_label.x0 - solicitation_value.x0) < 5.0
    assert solicitation_value.y0 > solicitation_label.y1


@requires_regression_pdf
def test_native_dict_mode_award_date_two_column_case() -> None:
    # Regression: "28. AWARD DATE" (right column) must be positioned
    # distinctly from "27. UNITED STATES OF AMERICA" (left column,
    # Contracting Officer signature block) at line granularity.
    doc = fitz.open(REGRESSION_PDF)
    page = doc[1]
    lines = lines_from_fitz_page(page=page, page_number=2)

    award_date_label = next(l for l in lines if "AWARD DATE" in l.text)
    us_label = next(l for l in lines if "UNITED STATES OF AMERICA" in l.text)

    assert award_date_label.x0 > us_label.x0 + 100


def test_synthetic_two_column_form_lines_stay_distinct() -> None:
    # Portable equivalent of the SF33 regression case - built in-memory so
    # it runs on any machine, not just one with the reference contract.
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((19, 50), "2. CONTRACT NUMBER", fontsize=8)
    page.insert_text((202, 50), "3. SOLICITATION NUMBER", fontsize=8)
    page.insert_text((19, 62), "47QRCA25DSF07", fontsize=8)
    page.insert_text((202, 62), "47QRCA23R0001", fontsize=8)

    lines = lines_from_fitz_page(page=page, page_number=1)
    texts = {l.text: l for l in lines}

    assert "2. CONTRACT NUMBER" in texts
    assert "3. SOLICITATION NUMBER" in texts
    # Distinct columns preserved, not merged into one block/line.
    assert texts["2. CONTRACT NUMBER"].x0 != texts["3. SOLICITATION NUMBER"].x0
    assert abs(texts["47QRCA25DSF07"].x0 - texts["2. CONTRACT NUMBER"].x0) < 5.0
    assert abs(texts["47QRCA23R0001"].x0 - texts["3. SOLICITATION NUMBER"].x0) < 5.0


def test_ocr_layout_lines_normalized() -> None:
    ocr_layout = {
        "lines": [
            {"text": "3. SOLICITATION NUMBER", "x0": 200.0, "y0": 46.0, "x1": 270.0, "y1": 52.0, "conf": 92.5},
            {"text": "47QRCA23R0001", "x0": 202.0, "y0": 53.0, "x1": 275.0, "y1": 63.0, "conf": 88.0},
        ]
    }
    lines = lines_from_ocr_layout(ocr_layout_json=ocr_layout, page_number=5)
    assert len(lines) == 2
    assert lines[0].source == "ocr_word_layer"
    assert lines[0].extraction_method == "ocr"
    assert lines[1].confidence == 88.0


def test_ocr_layout_empty_returns_empty() -> None:
    assert lines_from_ocr_layout(ocr_layout_json=None, page_number=1) == []
    assert lines_from_ocr_layout(ocr_layout_json={}, page_number=1) == []


def test_blocks_fallback_splits_multiline_block_interpolated() -> None:
    block = _block(
        "4. TYPE OF SOLICITATION\n2. CONTRACT NUMBER \n3. SOLICITATION NUMBER",
        x0=19.0, y0=46.6, x1=386.8, y1=53.7,
    )
    lines = lines_from_blocks_fallback(blocks=[block], page_number=2)
    assert len(lines) == 3
    assert all(l.source == "block_split_interpolated" for l in lines)
    # y should increase monotonically across the interpolated lines.
    assert lines[0].y0 < lines[1].y0 < lines[2].y0


def test_blocks_fallback_multiline_value_block_preserved() -> None:
    block = _block(
        "This is a long multi-line\nnarrative value spanning\nseveral wrapped lines",
        x0=72.0, y0=100.0, x1=500.0, y1=130.0,
    )
    lines = lines_from_blocks_fallback(blocks=[block], page_number=10)
    assert len(lines) == 3


def test_blocks_fallback_empty_block_produces_no_lines() -> None:
    block = _block("   \n  \n", x0=0.0, y0=0.0, x1=10.0, y1=10.0)
    lines = lines_from_blocks_fallback(blocks=[block], page_number=1)
    assert lines == []


@requires_regression_pdf
def test_best_available_lines_prefers_fitz_page_over_fallback() -> None:
    doc = fitz.open(REGRESSION_PDF)
    page = doc[1]
    fallback_block = _block("irrelevant fallback text", x0=0.0, y0=0.0, x1=10.0, y1=10.0)
    lines = best_available_lines(
        blocks=[fallback_block], page_number=2, fitz_page=page
    )
    assert any(l.source == "native_dict_span" for l in lines)


def test_best_available_lines_prefers_ocr_layout_over_fallback_when_no_fitz_page() -> None:
    ocr_layout = {
        "lines": [{"text": "OCR line", "x0": 0.0, "y0": 0.0, "x1": 50.0, "y1": 10.0, "conf": 90.0}]
    }
    fallback_block = _block("irrelevant fallback text", x0=0.0, y0=0.0, x1=10.0, y1=10.0)
    lines = best_available_lines(
        blocks=[fallback_block], page_number=1, ocr_layout_json=ocr_layout
    )
    assert lines[0].source == "ocr_word_layer"


def test_best_available_lines_uses_fallback_when_nothing_else_available() -> None:
    block = _block("Label Only\nValue Below", x0=0.0, y0=0.0, x1=100.0, y1=20.0)
    lines = best_available_lines(blocks=[block], page_number=1)
    assert lines
    assert all(l.source == "block_split_interpolated" for l in lines)
