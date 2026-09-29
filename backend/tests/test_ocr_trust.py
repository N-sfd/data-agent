"""OCR trust rules for Verified: they apply to OCR-read evidence only, flag
(never rewrite) values, and keep native PDF / HTML verification as is.
Plus the structural rules that keep table content out of wrong cells."""

from __future__ import annotations

from app.services.ocr_word_layer import OcrLayout, OcrWord, fuse_layouts
from app.source_structure.pdf_structure import Line, Segment, Word, _Ids, _raster_grid_table
from app.source_structure.raster_tables import RasterGrid
from app.staging.models import CellProvenance, StagingCell, StagingDataset, StagingRecord, StagingWorkbook
from app.staging.profile import FieldDefinition
from app.staging.profiles.invoice_v1 import _split_code
from app.staging.service import _with_ocr_notice
from app.staging.validation import evaluate_cell


def _prov(evidence: str, *, gate: bool, confidence: float | None = 0.95, contested: bool = False) -> CellProvenance:
    return CellProvenance(
        source_document_id="d",
        source_filename="f.png",
        source_type="image" if gate else "pdf",
        source_page=1,
        evidence_text=evidence,
        ocr_gate=gate,
        ocr_confidence=confidence if gate else None,
        ocr_contested=contested,
    )


def _state(value: str, provenance: CellProvenance, value_type: str = "text"):
    definition = FieldDefinition("t.value", "value", "Value", value_type)
    _, status, reasons = evaluate_cell(definition, value, provenance, record_flagged=False)
    return status, reasons


# --- scope: OCR rules never touch native PDF / HTML ---------------------------------------


def test_native_and_html_values_do_not_need_ocr_confidence():
    native = _prov("TARIQMAHMOODKHAN", gate=False)
    assert _state("TARIQMAHMOODKHAN", native) == ("Verified", [])
    html = native.model_copy(update={"source_type": "html"})
    assert _state("TARIQMAHMOODKHAN", html)[0] == "Verified"


def test_ocr_value_needs_known_high_confidence():
    assert _state("GENERAL", _prov("GENERAL", gate=True, confidence=0.95))[0] == "Verified"
    assert _state("GENERAL", _prov("GENERAL", gate=True, confidence=0.79))[0] == "Needs Review"
    assert _state("GENERAL", _prov("GENERAL", gate=True, confidence=None))[0] == "Needs Review"


# --- contested readings, ruling artifacts, merged words -------------------------------------


def test_ocr_pass_disagreement_blocks_verified_even_when_confident():
    status, reasons = _state("067", _prov("067", gate=True, confidence=0.93, contested=True))
    assert status == "Needs Review"
    assert any("OCR passes read this value differently" in r for r in reasons)


def test_fusion_marks_disagreeing_words_contested():
    a = OcrLayout(words=[OcrWord("067", 0.93, 0, 0, 30, 10, 1, 1, 1)], lines=[], mean_word_confidence=0.93)
    b = OcrLayout(words=[OcrWord("057", 0.91, 0, 0, 30, 10, 1, 1, 1)], lines=[], mean_word_confidence=0.91)
    same = OcrLayout(words=[OcrWord("067", 0.90, 0, 0, 30, 10, 1, 1, 1)], lines=[], mean_word_confidence=0.9)
    assert fuse_layouts(a, b).words[0].contested is True
    assert fuse_layouts(a, same).words[0].contested is False


def test_ruling_line_artifacts_are_flagged_not_stripped():
    status, reasons = _state("2. _|", _prov("2. _|", gate=True))
    assert status == "Needs Review" and any("line/box artifacts" in r for r in reasons)
    assert _state("2.", _prov("2.", gate=True))[0] == "Verified"
    assert _state("ABC_123", _prov("ABC_123", gate=True))[0] == "Verified"  # underscore inside a code


def test_merged_word_rule_is_for_free_text_not_identifiers():
    assert _state("TARIQMAHMOOD", _prov("TARIQMAHMOOD", gate=True))[0] == "Needs Review"
    assert _state("NS20261048", _prov("NS20261048", gate=True))[0] == "Verified"
    assert _state("ABCDEFGHIJKLMN", _prov("ABCDEFGHIJKLMN", gate=True), value_type="code")[0] == "Verified"


# --- enhanced OCR unavailable: plain-language QA, no state change --------------------------


def _workbook_with_qa() -> StagingWorkbook:
    qa = StagingDataset(
        dataset_id="qa_review", display_name="QA Review", cardinality="repeating", role="qa",
        columns=[], records=[],
    )
    for suffix in ("check", "result", "details", "action"):
        qa.columns.append(
            {"canonical_field": f"qa.{suffix}", "key": suffix, "display_label": suffix.title()}  # type: ignore[arg-type]
        )
    qa = StagingDataset.model_validate(qa.model_dump())
    return StagingWorkbook.model_validate(
        {
            "document_id": "d", "document_filename": "f.png",
            "profile": {"profile_id": "p", "profile_version": 1, "display_name": "P", "description": "",
                        "document_families": [], "export_capabilities": []},
            "outcome": {"status": "populated", "title": "", "message": ""},
            "datasets": [qa.model_dump()],
            "qa_summary": {}, "processing_metadata": {},
        }
    )


def test_enhanced_ocr_unavailable_adds_a_plain_language_note():
    workbook = _with_ocr_notice(_workbook_with_qa(), {"enhancement": [1], "word_layer": []})
    record: StagingRecord = workbook.datasets[0].records[-1]
    details = record.cells["qa.details"].value
    assert "Enhanced OCR was unavailable (page 1)" in details
    assert "primary OCR pass" in details and "Traceback" not in details
    untouched = _with_ocr_notice(_workbook_with_qa(), {"enhancement": [], "word_layer": []})
    assert untouched.datasets[0].records == []


# --- invoice part numbers: column semantics before lexical shape --------------------------


def test_alphabetic_part_number_needs_column_evidence():
    assert _split_code("TRV Travel and mileage") == (None, "TRV Travel and mileage")
    assert _split_code("TRV Travel and mileage", column_leads_with_codes=True) == ("TRV", "Travel and mileage")
    assert _split_code("P-100 Premium copy paper") == ("P-100", "Premium copy paper")
    # Lowercase / long words are never taken as codes.
    assert _split_code("Travel and mileage", column_leads_with_codes=True)[0] is None


# --- table structure: a printed row rule always separates rows ------------------------------


def _line(index: int, words: list[Word]) -> Line:
    return Line(index=index, words=words, segments=[Segment(words=words, line_index=index)])


def test_numbered_empty_row_is_not_merged_into_the_total_row_across_a_rule():
    grid = RasterGrid(
        columns=[0, 40, 200, 260, 320], top=0, bottom=120,
        row_rules=[(0, 30, 320, 30), (0, 60, 320, 60), (0, 90, 320, 90)],
    )
    lines = [
        _line(0, [Word("Sr.", 5, 10, 25, 20, 8), Word("SUBJECTS", 60, 10, 120, 20, 8), Word("Max", 210, 10, 240, 20, 8), Word("Obt", 270, 10, 300, 20, 8)]),
        _line(1, [Word("7.", 5, 40, 15, 50, 8), Word("SOCIOLOGY", 60, 40, 130, 50, 8), Word("200", 210, 40, 240, 50, 8), Word("141", 270, 40, 300, 50, 8)]),
        _line(2, [Word("8.", 5, 70, 15, 80, 8)]),
        _line(3, [Word("TOTAL", 60, 100, 110, 110, 8), Word("1100", 210, 100, 245, 110, 8), Word("0680", 270, 100, 305, 110, 8)]),
    ]
    table, _ = _raster_grid_table(_Ids(1), 1, lines, grid, "ocr", "")
    rows = [[c.text for c in row] for row in table.rows]
    assert ["8.", "", "", ""] in rows
    assert ["", "TOTAL", "1100", "0680"] in rows


def test_without_row_rules_split_figures_still_complete_their_row():
    # A tilted scan with no usable row rules: the figures on the line under
    # the identifier still belong to that row (previous behaviour).
    grid = RasterGrid(columns=[0, 40, 200, 260, 320], top=0, bottom=120)
    lines = [
        _line(0, [Word("Sr.", 5, 10, 25, 20, 8), Word("SUBJECTS", 60, 10, 120, 20, 8), Word("Max", 210, 10, 240, 20, 8), Word("Obt", 270, 10, 300, 20, 8)]),
        _line(1, [Word("1.", 5, 40, 15, 50, 8), Word("ENGLISH", 60, 40, 130, 50, 8)]),
        _line(2, [Word("200", 210, 52, 240, 62, 8), Word("069", 270, 52, 300, 62, 8)]),
        _line(3, [Word("2.", 5, 80, 15, 90, 8), Word("URDU", 60, 80, 110, 90, 8), Word("200", 210, 80, 240, 90, 8), Word("129", 270, 80, 300, 90, 8)]),
    ]
    table, _ = _raster_grid_table(_Ids(1), 1, lines, grid, "ocr", "")
    assert [[c.text for c in row] for row in table.rows][0] == ["1.", "ENGLISH", "200", "069"]


def test_unused_ocr_keys_are_not_serialized():
    native = CellProvenance(source_document_id="d", source_filename="f.pdf", source_type="pdf").model_dump()
    assert not {"ocr_confidence", "ocr_gate", "ocr_contested"} & native.keys()
    ocr = _prov("x", gate=True, contested=True).model_dump()
    assert ocr["ocr_gate"] is True and ocr["ocr_contested"] is True
    cell = StagingCell(canonical_field="a.b", display_label="B")
    assert cell.model_dump()["provenance"] is None
