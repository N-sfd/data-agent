"""FAR_REGULATION: what a FAR record is, what it prescribes, what it cites.

One rule for every FAR Part (1–53), never per-Part logic:

* Record Type — the record's regulatory function, read from its text
  first (a definitions list, a clause prescription, a form prescription)
  and its official heading second (Policy, Responsibility, Limitation …).
* Prescriptions — in Parts 1–51 and 53, the paragraphs that instruct the
  contracting officer to insert / use a provision, clause or form, and the
  52.xxx-x / form numbers they name ("51.107 → 52.251-1").
* Cross references — explicit FAR, CFR, U.S.C., Public Law, Executive
  Order and form citations, typed; shown in one column, kept structured.
* Part 53 — form number, name, type, prescribing FAR reference, usage and
  supersession, only when the record is about a form.

Nothing is invented: a value is filled only when the source text states it.
Deterministic — no AI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

RECORD_TYPES = (
    "Scope", "Definition", "Policy", "General", "Procedure", "Requirement", "Responsibility", "Applicability",
    "Authority", "Guidance", "Limitation", "Exception", "Approval", "Determination", "Waiver",
    "Contract Clause Prescription", "Solicitation Provision Prescription", "Provision & Clause Prescription",
    "Form Prescription", "Reporting Requirement", "Recordkeeping Requirement", "Payment", "Pricing", "Funding",
    "Contract Administration", "Reserved", "Other",
)

_CLAUSE_NUMBER = r"52\.\d{3}-\d{1,3}"
_FORM = (
    r"(?:Standard\s+Forms?|Optional\s+Forms?|SF['’]?s?|OF['’]?s?|DD\s+Forms?|GSA\s+Forms?)\s*"
    r"\d{1,4}[A-Z]?(?:-\d+)?(?:\s*(?:,|and|or)\s*\d{1,4}[A-Z]?(?:-\d+)?)*"
)
# An instruction to insert / use a provision, clause or form.
_PRESCRIBES = re.compile(
    r"\b(?:shall|must|may|should)\s+(?:also\s+)?(?:insert|include|use|incorporate|prescribe)|"
    r"\b(?:insert|use)\s+the\s+(?:provisions?|clauses?)\b|"
    r"\b(?:is|are)\s+prescribed\b|\bprescribed\s+(?:in|at|for)\b|"
    r"\b(?:shall|must)\s+be\s+used\b",
    re.I,
)
_PROVISION_WORD = re.compile(r"\bprovisions?\b", re.I)
_CLAUSE_WORD = re.compile(r"\bclauses?\b", re.I)
_PARAGRAPH_SPLIT = re.compile(r"\n+")

_REFERENCES: tuple[tuple[str, re.Pattern], ...] = (
    ("CFR", re.compile(r"\b\d{1,2}\s+CFR\s+(?:[Pp]arts?\s+|[Ss]ubparts?\s+|§+\s*)?\d+(?:\.\d+)?(?:-\d+)?(?:\([a-z0-9]+\))*")),
    ("USC", re.compile(r"\b\d{1,2}\s+U\.\s?S\.\s?C\.\s+(?:§+\s*)?\d+[a-z]?(?:[–-]\d+[a-z]?)?(?:\([a-zA-Z0-9]+\))*")),
    ("Public Law", re.compile(r"\b(?:Pub(?:lic)?\.?\s*L(?:aw)?\.?)\s+\d{2,3}[–-]\d+")),
    ("Executive Order", re.compile(r"\b(?:Executive\s+Order|E\.\s?O\.)\s+\d{5}")),
    ("Form", re.compile(r"\b" + _FORM)),
    ("FAR", re.compile(
        r"\b(?:[Ss]ubpart\s+\d{1,2}\.\d{1,2}(?!\d)|[Pp]art\s+\d{1,2}(?![\d.])|"
        r"\d{1,2}\.\d{3,4}(?:-\d{1,4})?(?:\([a-zA-Z0-9]{1,4}\))*)"
    )),
)
_REFERENCE_ORDER = ("FAR", "CFR", "USC", "Public Law", "Executive Order", "Form")


@dataclass(frozen=True)
class Reference:
    kind: str  # FAR | CFR | USC | Public Law | Executive Order | Form
    text: str  # as cited, whitespace normalized


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def typed_references(text: str | None, own_number: str | None = None) -> list[Reference]:
    """Explicit citations in source order, typed, without the record's own
    number. FAR citations inside a CFR / U.S.C. citation are not FAR."""

    if not text:
        return []
    found: list[tuple[int, Reference]] = []
    taken: list[tuple[int, int]] = []
    for kind, pattern in _REFERENCES:
        for match in pattern.finditer(text):
            span = match.span()
            if any(span[0] < end and start < span[1] for start, end in taken):
                continue
            cited = _norm(match.group(0)).rstrip(".,;")
            if kind == "FAR":
                if own_number and cited.split("(")[0] == own_number:
                    continue
                # "41 U.S.C. 1707"-style numbers are claimed above; a bare
                # decimal such as "1.5" is not a FAR section.
                if not re.search(r"\d\.\d{3}|[Ss]ubpart|[Pp]art", cited):
                    continue
            taken.append(span)
            found.append((span[0], Reference(kind, cited)))
    seen: set[tuple[str, str]] = set()
    out: list[Reference] = []
    for _, ref in sorted(found, key=lambda item: item[0]):
        key = (ref.kind, ref.text.lower())
        if key not in seen:
            seen.add(key)
            out.append(ref)
    return out


def references_text(references: list[Reference]) -> str | None:
    """One Cross References cell: FAR citations first, then the other kinds."""

    ordered = sorted(references, key=lambda r: _REFERENCE_ORDER.index(r.kind))
    return "; ".join(r.text for r in ordered) or None


@dataclass
class Prescription:
    usage: str  # the prescribing paragraph(s), verbatim
    references: list[str]  # 52.xxx-x and form numbers, in source order
    kind: str  # one of the prescription Record Types


def prescriptions(text: str | None) -> Prescription | None:
    """The paragraphs of a Part 1–51 / 53 record that prescribe a provision,
    clause or form, with what they prescribe."""

    if not text:
        return None
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]
    chosen: list[str] = []
    refs: list[str] = []
    provisions = clauses = forms = False
    for paragraph in paragraphs:
        clause_numbers = re.findall(_CLAUSE_NUMBER, paragraph)
        form_numbers = [_norm(m.group(0)) for m in re.finditer(r"\b" + _FORM, paragraph)]
        if not (clause_numbers or form_numbers) or not _PRESCRIBES.search(paragraph):
            continue
        chosen.append(paragraph)
        for ref in clause_numbers + form_numbers:
            if ref not in refs:
                refs.append(ref)
        if clause_numbers:
            provisions = provisions or bool(_PROVISION_WORD.search(paragraph))
            clauses = clauses or bool(_CLAUSE_WORD.search(paragraph))
        if form_numbers and not clause_numbers:
            forms = True
    if not chosen:
        return None
    if provisions and clauses:
        kind = "Provision & Clause Prescription"
    elif provisions:
        kind = "Solicitation Provision Prescription"
    elif clauses:
        kind = "Contract Clause Prescription"
    elif forms:
        kind = "Form Prescription"
    else:
        kind = "Contract Clause Prescription"
    return Prescription("\n".join(chosen), refs, kind)


# Heading words → regulatory function, most specific first.
_HEADING_TYPES: tuple[tuple[str, str], ...] = (
    (r"\bdefinitions?\b", "Definition"),
    (r"^scope\b|\bscope of (?:part|subpart|section)\b", "Scope"),
    (r"\bwaivers?\b", "Waiver"),
    (r"\bexceptions?\b|\bexemptions?\b|\bexclusions?\b", "Exception"),
    (r"\blimitations?\b|\brestrictions?\b|\bprohibitions?\b", "Limitation"),
    (r"\bapprovals?\b", "Approval"),
    (r"\bdeterminations?\b|\bfindings\b", "Determination"),
    (r"\breport(?:s|ing)?\b", "Reporting Requirement"),
    (r"\brecords?\b|\brecordkeeping\b|\bcontract files?\b|\bdocumentation\b", "Recordkeeping Requirement"),
    (r"\bpayments?\b|\binvoic", "Payment"),
    (r"\bpricing\b|\bprice (?:analysis|reasonableness|negotiation|adjustment)|\bcost or pricing\b|\bcost (?:analysis|principles)\b", "Pricing"),
    (r"\bfunding\b|\bfunds?\b|\bappropriat", "Funding"),
    (r"\bresponsibilit", "Responsibility"),
    (r"\bauthorit|\bdelegation\b", "Authority"),
    (r"\bapplicab|\bapplication\b|\bcoverage\b", "Applicability"),
    (r"\bpolic(?:y|ies)\b", "Policy"),
    (r"\bprocedures?\b|\bprocess(?:ing)?\b|\bsteps\b", "Procedure"),
    (r"\brequirements?\b|\bstandards?\b|\bcriteria\b|\bconditions\b", "Requirement"),
    (r"\badministration\b|\bmodifications?\b|\btermination\b|\bclose-?out\b", "Contract Administration"),
    (r"\bguidance\b|\bdescription\b|\bconsiderations\b|\bfactors\b", "Guidance"),
    (r"\bgeneral\b|\bpurpose\b|\bintroduction\b", "General"),
)
_DEFINITION_TEXT = re.compile(r"^\s*(?:\(\w+\)\s*)?As used in this (?:part|subpart|section|subsection)\b", re.I)


def classify_record(title: str | None, text: str | None, prescription: Prescription | None, reserved: bool = False) -> str:
    """The record's regulatory function. The text decides first (a
    definitions list, a prescription), then the official heading."""

    if reserved:
        return "Reserved"
    heading = (title or "").strip().lower()
    body = text or ""
    if _DEFINITION_TEXT.match(body) or re.search(r"\bdefinitions?\b", heading):
        return "Definition"
    if re.match(r"^scope\b", heading):
        return "Scope"
    heading_kind = next((kind for pattern, kind in _HEADING_TYPES if re.search(pattern, heading)), None)
    if prescription is not None:
        # A clause / provision prescription defines the record; a form
        # mentioned in, e.g., an "Authorization" section does not.
        if prescription.kind != "Form Prescription" or heading_kind is None:
            return prescription.kind
    if heading_kind:
        return heading_kind
    if not body.strip():
        return "Other"
    if re.search(r"\b(?:shall|must)\b", body):
        return "Requirement"
    if re.search(r"\b(?:should|may)\b", body):
        return "Guidance"
    return "Other"


# --- Part 53: forms ---------------------------------------------------------------------------

_FORM_TITLE = re.compile(
    r"^(?P<kind>Standard Form|Optional Form|SF|OF|DD Form|GSA Form)\s*(?P<number>\d{1,4}[A-Z]?(?:-\d+)?)\s*,?\s*(?P<name>.*)$",
    re.I,
)
_FORM_KINDS = {"sf": "Standard Form", "of": "Optional Form", "standard form": "Standard Form", "optional form": "Optional Form",
               "dd form": "DD Form", "gsa form": "GSA Form"}
_SUPERSEDES = re.compile(r"[^.]*\b(?:supersed\w*|replac\w*|previous editions?|obsolete|no longer (?:used|authorized))\b[^.]*\.", re.I)
_PRESCRIBED_IN = re.compile(r"\b(?:prescribed|specified|required|as (?:provided|stated))\s+(?:in|at|by)\s+(?:FAR\s+)?(?P<ref>(?:subpart\s+)?\d{1,2}\.\d{1,4}(?:-\d+)?(?:\([a-z0-9]+\))*)", re.I)


@dataclass
class FormInfo:
    number: str | None
    name: str | None
    form_type: str | None
    prescribing_reference: str | None
    usage: str | None
    supersession: str | None


def form_info(title: str | None, text: str | None) -> FormInfo | None:
    """A Part 53 record about a form: "53.301-1449 Standard Form 1449,
    Solicitation/Contract/Order …", or a 53.2xx record listing the forms
    a FAR subject prescribes ("… (SF's 18, 30, 1449)")."""

    title = (title or "").strip().rstrip(".")
    body = text or ""
    number = name = form_type = None
    if match := _FORM_TITLE.match(title):
        form_type = _FORM_KINDS.get(match.group("kind").lower(), match.group("kind"))
        prefix = "SF" if form_type == "Standard Form" else "OF" if form_type == "Optional Form" else form_type
        number = f"{prefix} {match.group('number')}"
        name = match.group("name").strip() or None
    else:
        listed = re.findall(r"\b" + _FORM, title)
        if not listed:
            return None
        number = "; ".join(_norm(f) for f in listed)
        kinds = {_FORM_KINDS.get(re.sub(r"['’]?s$", "", f.split()[0].lower()).rstrip("'’"), None) for f in listed}
        kinds.discard(None)
        form_type = "; ".join(sorted(kinds)) or None
    prescribed = _PRESCRIBED_IN.search(body)
    supersession = _SUPERSEDES.search(body)
    first_sentence = re.split(r"(?<=[.;])\s", body.strip(), maxsplit=1)[0] if body.strip() else None
    return FormInfo(
        number=number,
        name=name,
        form_type=form_type,
        prescribing_reference=prescribed.group("ref") if prescribed else None,
        usage=first_sentence,
        supersession=_norm(supersession.group(0)) if supersession else None,
    )


def part_title(part_heading: str | None) -> str | None:
    """"Part 15 - Contracting by Negotiation" → "Contracting by Negotiation"."""

    if not part_heading:
        return None
    match = re.match(r"^\s*Part\s+\d{1,2}\s*[-–—:]\s*(?P<title>.+)$", part_heading, re.I)
    return match.group("title").strip() if match else None
