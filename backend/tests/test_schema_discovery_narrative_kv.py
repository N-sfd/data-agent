"""Regression: narrative KV promotion must not crash schema discovery."""

from app.schemas.structure_detection import DetectedTarget
from app.services.structure_detection import _target


def test_section_marker_uses_valid_extraction_type() -> None:
    """Narrative KV reroutes must use a valid ExtractionType literal."""

    target = _target(
        key="section_b_1_general",
        label="B.1 General",
        extraction_type="clause",
        pages=[2],
        confidence=0.85,
        evidence=["section marker"],
    )
    assert isinstance(target, DetectedTarget)
    assert target.extraction_type == "clause"

    # "section" is not a valid ExtractionType — would 500 discover-schema.
    try:
        _target(
            key="section_bad",
            label="Bad",
            extraction_type="section",  # type: ignore[arg-type]
            pages=[1],
            confidence=0.5,
            evidence=[],
        )
        raised = False
    except Exception:
        raised = True
    assert raised
