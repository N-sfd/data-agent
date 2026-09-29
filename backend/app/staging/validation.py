"""Universal cell validation → the three user-facing states.

    Missing       the profile expects the field; no source-supported value
    Needs Review  a value exists, but a check failed or the record is flagged
    Verified      evidence exists, the value is grounded in it, its type and
                  field rules pass, and its record is not flagged

Confidence scores (OCR or extraction) are deliberately NOT an input: a
perfectly-read "$0.00" next to "Minimum Guarantee" is still wrong if the
evidence doesn't say it's the minimum guarantee.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.staging.models import (
    MISSING,
    NEEDS_REVIEW,
    VERIFIED,
    CellProvenance,
    CellValidation,
    ReviewStatus,
    ValidationCheck,
)
from app.staging.profile import FieldDefinition

NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
# Money: optional sign/parentheses, a currency symbol or ISO code on either
# side, and a plain or thousands-separated amount.
_MONEY_VALUE_RE = re.compile(
    r"^\(?-?\s*(?:[$\u20ac\u00a3\u00a5]|[A-Z]{3})?\s*-?[\d,]+(?:\.\d+)?\s*(?:[A-Z]{3})?\)?$"
)
_DATE_FORMATS = (
    "%m/%d/%Y",
    "%m/%d/%y",
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%Y%m%d",
)


def is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def to_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    negative = (text.startswith("(") and text.endswith(")")) or text.startswith("-")
    match = NUMBER_RE.search(text)
    if not match:
        return None
    try:
        number = float(match.group(0).replace(",", ""))
    except ValueError:
        return None
    return -number if negative else number


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def value_in_evidence(value: object, evidence: str, value_type: str) -> bool:
    """Is the value literally supported by the evidence text?

    Numbers compare numerically (a stored 2500.0 is supported by
    "$2,500.00"). Text must appear on token boundaries, so a truncated
    "$47.0" is NOT supported by "$47.0M"."""

    if value_type in ("money", "number", "integer") or isinstance(value, (int, float)):
        target = to_number(value)
        if target is None:
            return False
        for match in NUMBER_RE.finditer(evidence):
            try:
                # Magnitudes: a stored "-1,335.00" discount is supported by
                # evidence that shows the sign elsewhere ("Discount: -€1,335.00").
                if abs(abs(float(match.group(0).replace(",", ""))) - abs(target)) < 0.005:
                    return True
            except ValueError:
                continue
        return False

    needle = _collapse(str(value))
    if not needle:
        return False
    pattern = r"(?<![0-9a-z])" + re.escape(needle) + r"(?![0-9a-z])"
    return re.search(pattern, _collapse(evidence)) is not None


def _type_check(value: object, value_type: str) -> ValidationCheck | None:
    if value_type == "text":
        return None
    if value_type in ("money", "number"):
        ok = isinstance(value, (int, float)) or bool(
            isinstance(value, str) and _MONEY_VALUE_RE.match(value.strip())
        )
        return ValidationCheck(
            check="type", passed=ok, message=None if ok else f"Not a valid {value_type} value."
        )
    if value_type == "integer":
        number = to_number(value)
        ok = number is not None and float(number).is_integer()
        return ValidationCheck(
            check="type", passed=ok, message=None if ok else "Not a whole number."
        )
    if value_type == "date":
        text = str(value).strip()
        ok = False
        for fmt in _DATE_FORMATS:
            try:
                datetime.strptime(text, fmt)
                ok = True
                break
            except ValueError:
                continue
        return ValidationCheck(
            check="type", passed=ok, message=None if ok else "Not a recognizable date."
        )
    if value_type == "code":
        ok = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-/ ]*", str(value).strip()))
        return ValidationCheck(
            check="type", passed=ok, message=None if ok else "Not a valid code."
        )
    return None


def _rule_checks(
    definition: FieldDefinition, value: object, evidence: str
) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    for rule in definition.rules:
        if rule.rule == "positive_amount":
            number = to_number(value)
            ok = number is not None and number > 0
            checks.append(
                ValidationCheck(
                    check="positive_amount",
                    passed=ok,
                    message=None if ok else (rule.message or "Amount must be greater than zero."),
                )
            )
        elif rule.rule == "evidence_mentions":
            lowered = evidence.casefold()
            ok = any(term.casefold() in lowered for term in rule.terms)
            checks.append(
                ValidationCheck(
                    check="evidence_mentions",
                    passed=ok,
                    message=None
                    if ok
                    else (
                        rule.message
                        or f"Evidence does not mention {' / '.join(rule.terms)}."
                    ),
                )
            )
        elif rule.rule == "pattern" and rule.pattern:
            ok = re.fullmatch(rule.pattern, str(value).strip()) is not None
            checks.append(
                ValidationCheck(
                    check="pattern",
                    passed=ok,
                    message=None if ok else (rule.message or "Value has an unexpected format."),
                )
            )
    return checks


# An OCR-read value's words must all reach this confidence before it can be
# Verified (with source evidence and type checks as well).
OCR_VERIFY_MIN_CONFIDENCE = 0.80

# Glyphs OCR produces from table rules / box edges: any vertical bar, or a
# token made only of underscores/brackets.
_RULING_ARTIFACT = re.compile(r"[|¦]|(?:^|\s)[_\[\]]+(?:\s|$)")


def evaluate_cell(
    definition: FieldDefinition,
    value: object,
    provenance: CellProvenance | None,
    *,
    record_flagged: bool,
    profile_checks: list[ValidationCheck] | None = None,
) -> tuple[CellValidation, ReviewStatus | None, list[str]]:
    """`profile_checks` are extra checks a profile ran for this cell (e.g.
    semantic label mapping, line arithmetic); any failure means Needs
    Review, exactly like the built-in checks."""
    if definition.grounding == "none":
        return CellValidation(status="not_checked"), None, []

    if is_empty(value):
        if definition.expected:
            return (
                CellValidation(status="not_checked"),
                MISSING,
                ["No source-supported value was found for this field."],
            )
        return CellValidation(status="not_checked"), None, []

    if definition.grounding == "system":
        return CellValidation(status="passed"), VERIFIED, []

    evidence = (provenance.evidence_text if provenance else None) or ""
    checks: list[ValidationCheck] = []

    has_evidence = bool(evidence.strip())
    checks.append(
        ValidationCheck(
            check="has_evidence",
            passed=has_evidence,
            message=None if has_evidence else "No source evidence recorded for this value.",
        )
    )
    if has_evidence and definition.grounding == "evidence":
        grounded = value_in_evidence(value, evidence, definition.value_type)
        checks.append(
            ValidationCheck(
                check="grounded_in_evidence",
                passed=grounded,
                message=None
                if grounded
                else "Value does not appear as-is in its source evidence.",
            )
        )
    if provenance is not None and provenance.ocr_gate:
        # OCR often drops the space between capitalised words and still
        # reports high confidence ("TARIQMAHMOOD"): a long all-caps run of
        # LETTERS with no space is a merge until someone confirms it. Only
        # free text is checked — identifiers/codes ("NS20261048"), numbers
        # and dates follow no human word-spacing, and a value with digits is
        # not a run of words.
        text = str(value).strip()
        letters = [ch for ch in text if ch.isalpha()]
        merged = (
            definition.value_type == "text"
            and " " not in text
            and not any(ch.isdigit() for ch in text)
            and len(letters) >= 12
            and all(ch.isupper() for ch in letters)
        )
        checks.append(
            ValidationCheck(
                check="ocr_word_spacing",
                passed=not merged,
                message="OCR may have merged words (no spaces) — confirm against the source image." if merged else None,
            )
        )
        # Table ruling lines and box edges are often read as glyphs ("2. _|")
        # with high confidence: a value carrying them is not clean text.
        artifact = bool(_RULING_ARTIFACT.search(text))
        checks.append(
            ValidationCheck(
                check="ocr_ruling_artifacts",
                passed=not artifact,
                message="The OCR value contains line/box artifacts (| or _) — confirm against the source image."
                if artifact
                else None,
            )
        )
        checks.append(
            ValidationCheck(
                check="ocr_pass_agreement",
                passed=not provenance.ocr_contested,
                message="The OCR passes read this value differently — confirm against the source image."
                if provenance.ocr_contested
                else None,
            )
        )
        confident = provenance.ocr_confidence is not None and provenance.ocr_confidence >= OCR_VERIFY_MIN_CONFIDENCE
        checks.append(
            ValidationCheck(
                check="ocr_confidence",
                passed=confident,
                message=None
                if confident
                else (
                    "OCR confidence for this value is unavailable — confirm against the source image."
                    if provenance.ocr_confidence is None
                    else f"Low OCR confidence ({provenance.ocr_confidence:.2f}) — confirm against the source image."
                ),
            )
        )
    type_check = _type_check(value, definition.value_type)
    if type_check is not None:
        checks.append(type_check)
    checks.extend(_rule_checks(definition, value, evidence))
    checks.extend(profile_checks or [])

    failed = [check for check in checks if not check.passed]
    reasons = [check.message for check in failed if check.message]
    if record_flagged:
        reasons.append("The record this value belongs to is flagged for review.")

    validation = CellValidation(status="failed" if failed else "passed", checks=checks)
    status: ReviewStatus = NEEDS_REVIEW if (failed or record_flagged) else VERIFIED
    return validation, status, reasons
