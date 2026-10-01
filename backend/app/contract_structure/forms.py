"""Government cover forms (SF1442, SF33, and other ruled "STANDARD FORM"
pages): every numbered box read by its drawn cell, kept under the label the
form prints ("5. REQUISITION/PURCHASE REQUEST NO.") and mapped to a
canonical id (contract.requisition_number).

Values are read spatially — never by text order — and a blank box yields
no field. Scanned forms without vector rules fall back to label-relative
columns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.contract_structure.lines import PageLines, Rule, compact, join_paragraphs
from app.services.line_model import LogicalLine

METHOD = "form_cell_geometry"

SOLICITATION_AWARD = "Solicitation & Award"
ISSUING_OFFICE = "Issuing Office"
CONTRACTOR = "Contractor / Offeror"
CONTACTS = "Contacts"
PERFORMANCE = "Performance"
FINANCIAL = "Financial / Administrative"
SECTION_ORDER = (SOLICITATION_AWARD, ISSUING_OFFICE, CONTRACTOR, CONTACTS, PERFORMANCE, FINANCIAL)


@dataclass(frozen=True)
class ContractField:
    field_id: str
    label: str
    source_label: str
    value: str
    section: str
    page: int
    bbox: tuple[float, float, float, float]
    evidence: str
    method: str = METHOD


@dataclass(frozen=True)
class _Map:
    pattern: str
    field_id: str
    section: str
    # Professional label used when the printed label is a sentence or too
    # generic to stand alone ("CALENDAR DAYS").
    label: str


# Printed label (item number stripped, compacted) -> canonical field. The
# first match wins; order specific before general.
_MAPPINGS: tuple[_Map, ...] = (
    _Map(r"^solicitation(no|number)", "contract.solicitation_number", SOLICITATION_AWARD, "Solicitation No."),
    _Map(r"^typeofsolicitation", "contract.solicitation_type", SOLICITATION_AWARD, "Type of Solicitation"),
    _Map(r"^dateissued", "contract.date_issued", SOLICITATION_AWARD, "Date Issued"),
    _Map(r"^pageofpages", "contract.page_of_pages", SOLICITATION_AWARD, "Page of Pages"),
    _Map(r"^contract(no|number)", "contract.contract_number", SOLICITATION_AWARD, "Contract No."),
    _Map(r"^requisition", "contract.requisition_number", SOLICITATION_AWARD, "Requisition/Purchase Request No."),
    _Map(r"^project(no|number)", "contract.project_number", SOLICITATION_AWARD, "Project No."),
    _Map(r"^thegovernmentrequiresperformance", "contract.solicitation_title", SOLICITATION_AWARD, "Requirement"),
    _Map(r"^awarddate", "contract.award_date", SOLICITATION_AWARD, "Award Date"),
    _Map(r"^(itemsaccepted|acceptedastoitems)", "contract.items_accepted", SOLICITATION_AWARD, "Items Accepted"),
    _Map(r"^issuedby", "contract.issued_by", ISSUING_OFFICE, "Issued By"),
    _Map(r"^addressofferto", "contract.address_offer_to", ISSUING_OFFICE, "Address Offer To"),
    _Map(r"^administeredby", "contract.administered_by", ISSUING_OFFICE, "Administered By"),
    _Map(r"^nameandaddressofofferor", "contract.offeror", CONTRACTOR, "Offeror"),
    _Map(r"^(nameandaddressofcontractor|contractor/offeror)", "contract.offeror", CONTRACTOR, "Contractor"),
    _Map(r"^telephone(no|number)", "contract.offeror_telephone", CONTRACTOR, "Offeror Telephone"),
    _Map(r"^remittanceaddress", "contract.remittance_address", CONTRACTOR, "Remittance Address"),
    _Map(r"^nameandtitleofperson", "contract.offeror_signatory", CONTRACTOR, "Authorized Signatory"),
    _Map(r"^offerdate", "contract.offer_date", CONTRACTOR, "Offer Date"),
    _Map(r"^nameofcontractingofficer", "contract.contracting_officer", CONTACTS, "Contracting Officer"),
    _Map(r"^amount", "contract.award_amount", FINANCIAL, "Amount"),
    _Map(r"^accountingandappropriation", "contract.accounting_data", FINANCIAL, "Accounting and Appropriation Data"),
    _Map(r"^paymentwillbemadeby", "contract.payment_office", FINANCIAL, "Payment Will Be Made By"),
    _Map(r"^submitinvoices", "contract.invoice_address", FINANCIAL, "Submit Invoices To"),
    _Map(r"^calendardays", "contract.bond_due_days", PERFORMANCE, "Bonds Due (Calendar Days)"),
    _Map(r"^thecontractormustfurnish", "contract.bonds_required", PERFORMANCE, "Performance and Payment Bonds Required"),
)

# Sub-items of "FOR INFORMATION CALL" and the offeror telephone.
_CONTACT_SUBITEMS = (
    (r"^name", "contract.information_contact_name", "Information Contact Name"),
    (r"^telephone", "contract.information_contact_telephone", "Information Contact Telephone"),
    (r"^e-?mail", "contract.information_contact_email", "Information Contact Email"),
)

_LABEL = re.compile(r"^\s*(?P<item>\d{1,2}\s?[A-Z]?|[A-Z])\.\s+(?P<rest>\S.*)$")
_INSTRUCTION = re.compile(r"\((?:if|include|type|see|title|the offeror|must|nsn|\d+ copies)[^)]*\)?", re.IGNORECASE)
_SUBHEADINGS = frozenset(
    {
        "code", "facilitycode", "facility", "areacode", "number", "ext.", "ext", "extension",
        "(hour)", "(date)", "(date).", "tel:", "fax:", "call:", "x", "date", "amendmentno.",
        "(signatureofcontractingofficer)", "(signatureofpersonauthorizedtosign)",
    }
)
_MARK = re.compile(r"^\s*X\s*$")
_MARKED = re.compile(r"^\s*X\s+(?P<option>\S.*)$")
_DATE = re.compile(
    r"^\d{1,2}[\s-][A-Za-z]{3,9}[\s-]\d{2,4}$|^\d{1,2}/\d{1,2}/\d{2,4}$|^[A-Za-z]{3,9}\.? \d{1,2},? \d{4}$"
)
_TIME = re.compile(r"^\d{1,2}:\d{2}\s*(?:[AaPp]\.?[Mm]\.?)?(?:\s*[A-Z]{2,4})?$")
_NUMBER = re.compile(r"^\d{1,4}$")


def is_form_page(page: PageLines) -> bool:
    text = compact(" ".join(line.text for line in page.lines))
    labels = sum(1 for line in page.lines if _LABEL.match(line.text))
    return ("standardform" in text or "solicitation,offer" in text) and labels >= 8


def _union(lines: list[LogicalLine]) -> tuple[float, float, float, float]:
    return (
        min(line.x0 for line in lines),
        min(line.y0 for line in lines),
        max(line.x1 for line in lines),
        max(line.y1 for line in lines),
    )


def _strip_item(text: str) -> str:
    match = _LABEL.match(text)
    return match.group("rest") if match else text


def _clean_label(text: str) -> str:
    """'8. ADDRESS OFFER TO (If other than Item 7)' -> '8. ADDRESS OFFER TO'."""
    text = _INSTRUCTION.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip(" :")


def _is_sentence(label: str) -> bool:
    words = _strip_item(label).split()
    lowercase = sum(1 for word in words if word.islower())
    return len(words) > 7 or lowercase >= 3


def _is_heading_line(line: LogicalLine) -> bool:
    text = line.text.strip()
    return (
        bool(_LABEL.match(text))
        or compact(text) in _SUBHEADINGS
        or (text.startswith("(") and text.endswith(")"))
        or text.endswith(":")
        or bool(_INSTRUCTION.fullmatch(text))
        or compact(text) == "pageofpages"
        or bool(re.match(r"^(offer|award)\(", compact(text)))
    )


class _Page:
    def __init__(self, page: PageLines) -> None:
        self.page = page
        self.lines = list(page.lines)
        self.h: list[Rule] = list(page.h_rules)
        self.v: list[Rule] = list(page.v_rules)
        self.ruled = len(self.h) >= 8 and len(self.v) >= 8

    # --- cells -----------------------------------------------------------
    def cell(self, label: LogicalLine) -> tuple[float, float, float, float]:
        if not self.ruled:
            return self._fallback_cell(label)
        cy = (label.y0 + label.y1) / 2
        cx = label.x0 + 4
        left = max((x for (y0, y1, x) in self.v if y0 - 1 <= cy <= y1 + 1 and x <= label.x0 + 2), default=0.0)
        right = min(
            (x for (y0, y1, x) in self.v if y0 - 1 <= cy <= y1 + 1 and x > label.x0 + 6), default=self.page.width
        )
        top = max((y for (x0, x1, y) in self.h if x0 - 1 <= cx <= x1 + 1 and y <= label.y0 + 2), default=0.0)
        bottom = min(
            (y for (x0, x1, y) in self.h if x0 - 1 <= cx <= x1 + 1 and y >= label.y1 - 1), default=self.page.height
        )
        return left, top, right, bottom

    def _fallback_cell(self, label: LogicalLine) -> tuple[float, float, float, float]:
        same_row = [
            line.x0 for line in self.lines
            if line is not label and abs(line.y0 - label.y0) <= 4 and _LABEL.match(line.text) and line.x0 > label.x0 + 5
        ]
        right = min(same_row, default=self.page.width) - 2
        below = [
            line.y0 for line in self.lines
            if line.y0 > label.y1 + 2 and _LABEL.match(line.text) and line.x0 < right and line.x1 > label.x0
        ]
        return label.x0 - 4, label.y0 - 1, right, min(below, default=label.y1 + 40) - 1

    def extend_down(self, box: tuple[float, float, float, float]) -> tuple[float, float, float, float] | None:
        """The box directly under a header-only cell (same left/right)."""
        left, _, right, bottom = box
        cx = left + 6
        below = [y for (x0, x1, y) in self.h if x0 - 1 <= cx <= x1 + 1 and y > bottom + 2]
        if not below:
            return None
        return left, bottom, right, min(below)

    def inside(self, box: tuple[float, float, float, float], exclude: LogicalLine | None = None) -> list[LogicalLine]:
        left, top, right, bottom = box
        return [
            line
            for line in self.lines
            if line is not exclude
            and left - 1 <= (line.x0 + line.x1) / 2 <= right + 1
            and top - 1 <= (line.y0 + line.y1) / 2 <= bottom + 1
        ]

    def right_of(self, anchor: LogicalLine, reach: float = 80.0) -> LogicalLine | None:
        candidates = [
            line
            for line in self.lines
            if line is not anchor
            and abs((line.y0 + line.y1) / 2 - (anchor.y0 + anchor.y1) / 2) <= 5
            and 0 <= line.x0 - anchor.x1 <= reach
            and not _is_heading_line(line)
        ]
        return min(candidates, key=lambda line: line.x0, default=None)


def _value_lines(lines: list[LogicalLine]) -> list[LogicalLine]:
    """Value lines of a box: headings, sub-headings and printed
    instructions — including a "(The offeror acknowledges …" parenthetical
    wrapped over several lines — removed."""
    values: list[LogicalLine] = []
    open_paren = False
    for line in sorted(lines, key=lambda line: (round(line.y0), line.x0)):
        text = line.text.strip()
        if open_paren:
            open_paren = ")" not in text
            continue
        if text.startswith("(") and ")" not in text:
            open_paren = True
            continue
        if not _is_heading_line(line):
            values.append(line)
    return values


def _checked(lines: list[LogicalLine], *, whole_row: bool = False) -> tuple[str, list[LogicalLine]] | None:
    """The option an X marks. `whole_row` takes every line right of the
    mark on its row (an option printed in pieces: "NEGOTIATED" "(RFP)");
    otherwise only the nearest option (rows of several checkboxes)."""
    for line in lines:
        marked = _MARKED.match(line.text)
        if marked:
            return marked.group("option").strip(), [line]
    for mark in (line for line in lines if _MARK.match(line.text)):
        options = [
            line for line in lines
            if not _MARK.match(line.text)
            and abs((line.y0 + line.y1) / 2 - (mark.y0 + mark.y1) / 2) <= 4
            and 0 <= line.x0 - mark.x1 <= 22
        ]
        if options and whole_row:
            row = sorted(
                (line for line in lines if not _MARK.match(line.text)
                 and abs((line.y0 + line.y1) / 2 - (mark.y0 + mark.y1) / 2) <= 4 and line.x0 >= mark.x1 - 1),
                key=lambda line: line.x0,
            )
            following = [
                line for line in lines
                if line not in row and abs(line.x0 - row[0].x0) <= 2 and 0 < line.y0 - row[0].y1 <= 4
            ]
            return " ".join(line.text for line in [*row, *following]).strip(), [mark, *row, *following]
        if options:
            option = min(options, key=lambda line: line.x0)
            following = [
                line for line in lines
                if line is not option and abs(line.x0 - option.x0) <= 2 and 0 < line.y0 - option.y1 <= 4
            ]
            text = " ".join(line.text for line in [option, *following])
            return text.strip(), [mark, option, *following]
    return None


def _solicitation_type(text: str) -> str:
    """'NEGOTIATED (RFP) REQUEST FOR PROPOSAL' -> 'Negotiated (RFP)'."""
    match = re.search(r"(sealed\s*bid|negotiated)\s*\((ifb|rfp)\)", text, re.IGNORECASE)
    if not match:
        match = re.search(r"(sealed\s*bid|negotiated)", text, re.IGNORECASE)
        return match.group(1).title() if match else text.strip()
    kind = "Sealed Bid" if "sealed" in match.group(1).lower() else "Negotiated"
    return f"{kind} ({match.group(2).upper()})"


def _map(label_text: str) -> _Map | None:
    key = compact(_strip_item(label_text))
    return next((mapping for mapping in _MAPPINGS if re.match(mapping.pattern, key)), None)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _strip_item(text).lower()).strip("_")[:60]


def read_form_page(page: PageLines) -> list[ContractField]:
    reader = _Page(page)
    fields: list[ContractField] = []
    seen: set[str] = set()
    part = SOLICITATION_AWARD

    def emit(field_id: str, label: str, source_label: str, value: str, section: str, used: list[LogicalLine], evidence: str | None = None) -> None:
        value = value.strip()
        if not value or not used or field_id in seen:
            return
        seen.add(field_id)
        fields.append(
            ContractField(
                field_id=field_id,
                label=label,
                source_label=source_label,
                value=value,
                section=section,
                page=page.page_number,
                bbox=_union(used),
                evidence=evidence or " ".join(line.text for line in used),
            )
        )

    # Form parts ("OFFER (…)", "AWARD (…)") decide where unmapped boxes go.
    part_marks = sorted(
        (line.y0, CONTRACTOR if compact(line.text).startswith("offer(") else FINANCIAL)
        for line in reader.lines
        if compact(line.text).startswith(("offer(", "award("))
    )

    labels = [line for line in reader.lines if _LABEL.match(line.text) or compact(line.text) == "pageofpages"]

    def resolve(label: LogicalLine) -> tuple[str, tuple[float, float, float, float], list[LogicalLine], bool]:
        """(full label text, value box, box contents, is a parent of
        lettered sub-items)."""
        box = reader.cell(label)
        contents = reader.inside(box, exclude=label)
        # Label words wrapped onto the next line ("...AUTHORIZED TO SIGN" /
        # "OFFER"): flush with the label, tight below it, letters only.
        wrapped = [
            line for line in contents
            if abs(line.x0 - label.x0) <= 3 and 0 <= line.y0 - label.y1 <= 3
            and re.fullmatch(r"[A-Za-z][A-Za-z /&:]{0,24}", line.text.strip()) and len(line.text.split()) <= 2
        ]
        label_text = " ".join([label.text, *(line.text for line in wrapped)])
        contents = [line for line in contents if line not in wrapped]
        # A label printed down a narrow box ("15A. NAME" / "AND" / "ADDRESS"
        # / "OF OFFEROR"): the value is in the box to its right.
        continuation = [line for line in contents if re.fullmatch(r"[A-Z][A-Z /&:]{0,24}", line.text.strip())]
        if (contents or wrapped) and len(continuation) == len(contents) and box[2] - box[0] < 140:
            label_text = " ".join([label_text, *(line.text for line in continuation)])
            right = min(
                (x for (y0, y1, x) in reader.v if y0 - 1 <= (box[1] + box[3]) / 2 <= y1 + 1 and x > box[2] + 4),
                default=page.width,
            )
            box = (box[2], box[1], right, box[3])
            contents = reader.inside(box)
            if any(re.match(r"^\s*[A-Z]\.\s", line.text) for line in contents):
                return label_text, box, [], True
            stops = [line.x0 for line in contents if _LABEL.match(line.text)]
            if stops:
                contents = [line for line in contents if line.x0 < min(stops) - 2]
        return label_text, box, contents, False

    resolved = {id(label): resolve(label) for label in labels}
    parents = [
        (reader.cell(label), _clean_label(resolved[id(label)][0]))
        for label in labels
        if resolved[id(label)][3]
    ]
    for label in labels:
        label_text, box, contents, is_parent = resolved[id(label)]
        if is_parent:
            continue
        # A container box (SF1442 item 13 with sub-items A-D) is read by
        # the anchored rules below, not as one value.
        if any(_LABEL.match(line.text) for line in contents) and not re.match(r"^\s*[A-Z]\.\s", label.text):
            continue
        source_label = _clean_label(label_text)
        is_checkbox_label = compact(_strip_item(label.text)).startswith("checkif")
        letter = re.match(r"^\s*([A-Z])\.\s", label.text)
        for y, name in part_marks:
            if label.y0 > y:
                part = name

        if letter:
            parent = next(
                (name for (pbox, name) in parents if pbox[1] - 2 <= (label.y0 + label.y1) / 2 <= pbox[3] + 2),
                None,
            )
            if parent is None:
                continue  # item 13 sub-clauses etc. are handled by anchors below
            key = compact(_strip_item(label.text))
            for pattern, field_id, fallback in _CONTACT_SUBITEMS:
                if re.match(pattern, key):
                    values = _value_lines(contents)
                    if not values:
                        extended = reader.extend_down(box)
                        values = _value_lines(reader.inside(extended)) if extended else []
                    emit(
                        field_id,
                        f"{parent} — {_clean_label(label.text)}",
                        f"{parent} {label.text}",
                        " ".join(line.text for line in sorted(values, key=lambda line: (round(line.y0), line.x0))),
                        CONTACTS,
                        values,
                    )
            continue

        mapping = _map(label_text)
        if mapping is None and _is_sentence(label_text):
            continue
        if is_checkbox_label and not any(_MARK.match(line.text) or _MARKED.match(line.text) for line in contents):
            continue
        # Header-only cells (value in the box beneath, e.g. 1. SOLICITATION
        # NO., 31C. AWARD DATE, B. TELEPHONE).
        values = _value_lines(contents)
        has_mark = any(_MARK.match(line.text) or _MARKED.match(line.text) for line in contents)
        is_type = bool(mapping and mapping.field_id == "contract.solicitation_type")
        extended = box
        for _ in range(3 if is_type else 1):
            if (values or has_mark) and not (is_type and not has_mark):
                break
            extended = reader.extend_down(extended)
            if not extended:
                break
            below = reader.inside(extended)
            if any(_LABEL.match(line.text) for line in below):
                break
            contents = [*contents, *below] if is_type else below
            values = _value_lines(contents)
            has_mark = any(_MARK.match(line.text) or _MARKED.match(line.text) for line in contents)

        # A CODE sub-box ("7. ISSUED BY  CODE N40192").
        code_label = next((line for line in contents if compact(line.text) == "code" or compact(line.text).startswith("code") and len(line.text.split()) == 2), None)
        base_id = mapping.field_id if mapping else f"contract.form.{_slug(label_text)}"
        if code_label is not None:
            inline = code_label.text.split()
            code_line = code_label if len(inline) == 2 else reader.right_of(code_label)
            code_value = inline[1] if len(inline) == 2 else (code_line.text if code_line else "")
            if code_line is not None:
                emit(f"{base_id}_code", f"{source_label} — CODE", f"{source_label} CODE", code_value,
                     mapping.section if mapping else part, [code_label, code_line] if code_line is not code_label else [code_label])
            values = [line for line in values if line is not code_line]

        if mapping and mapping.field_id == "contract.solicitation_type" or has_mark:
            hit = _checked(contents, whole_row=bool(mapping and mapping.field_id == "contract.solicitation_type"))
            if hit:
                option, used = hit
                if mapping and mapping.field_id == "contract.solicitation_type":
                    value = _solicitation_type(option)
                elif compact(option) in {"yes", "no"}:
                    value = option.strip().capitalize()
                else:
                    value = option
                display = mapping.label if mapping and _is_sentence(label_text) else source_label
                emit(base_id, display, source_label, value, mapping.section if mapping else part, used,
                     f"{label.text} {' '.join(line.text for line in used)}")
            continue

        if mapping and mapping.field_id == "contract.solicitation_title":
            # Keep "PROPOSAL DOCUMENTS:"-style headings; drop only the
            # printed "(Title, identifying no., date):" instruction.
            _emit_requirement(emit, label, [line for line in contents if not _INSTRUCTION.fullmatch(line.text.strip())
                                            and not (line.text.strip().startswith("(") and line.text.strip().endswith(":"))],
                              source_label)
            continue
        if mapping and mapping.field_id == "contract.page_of_pages":
            numbers = [
                re.sub(r"\D", "", line.text)
                for line in sorted(values, key=lambda line: line.x0)
                if re.fullmatch(r"\d+(\s*OF)?", line.text.strip(), re.IGNORECASE)
            ]
            if len(numbers) >= 2:
                emit(base_id, source_label, source_label, f"{numbers[0]} of {numbers[1]}", mapping.section, values)
            continue

        ordered = sorted(values, key=lambda line: (round(line.y0), line.x0))
        if not ordered:
            continue
        multiline = mapping is not None and mapping.section in (ISSUING_OFFICE, CONTRACTOR, FINANCIAL) and len(ordered) > 1
        value = "\n".join(line.text for line in ordered) if multiline else " ".join(line.text for line in ordered)
        if mapping and mapping.field_id == "contract.bond_due_days" and _NUMBER.match(value):
            value = f"{value} calendar days"
        display = mapping.label if mapping and (_is_sentence(label_text) or mapping.field_id == "contract.bond_due_days") else source_label
        emit(base_id, display, source_label, value, mapping.section if mapping else part, ordered)

    _anchored_fields(reader, emit)
    return fields


def _emit_requirement(emit, label: LogicalLine, values: list[LogicalLine], source_label: str) -> None:
    """Item 10 of the SF1442: the title paragraph, then the scope text."""
    ordered = sorted(values, key=lambda line: (round(line.y0), line.x0))
    title: list[LogicalLine] = []
    rest: list[LogicalLine] = []
    for line in ordered:
        if rest or (title and line.y0 - title[-1].y0 > max(1.6 * (title[-1].y1 - title[-1].y0), 15)):
            rest.append(line)
        else:
            title.append(line)
    emit("contract.solicitation_title", "Solicitation Title / Requirement", source_label,
         " ".join(line.text for line in title), SOLICITATION_AWARD, title)
    emit("contract.description_scope", "Description / Scope", source_label,
         join_paragraphs(rest), SOLICITATION_AWARD, rest)


def _anchored_fields(reader: _Page, emit) -> None:
    """Fields printed as sentences with blanks/checkboxes rather than boxes:
    performance start (SF1442 11), offer due time/date (SF1442 13A, SF33 9),
    offer guarantee (13B), acceptance period (13D)."""
    lines = reader.lines

    def find(prefix: str) -> LogicalLine | None:
        target = compact(prefix)
        return next((line for line in lines if compact(line.text).startswith(target)), None)

    item11 = find("11. The Contractor shall begin")
    if item11:
        row = [line for line in lines if 0 < line.y0 - item11.y1 <= 30]
        if row:
            first = min(line.y0 for line in row)
            row = [line for line in row if line.y0 - first <= 4]
        start: list[str] = []
        period: list[str] = []
        used: list[LogicalLine] = []
        for mark in (line for line in row if _MARK.match(line.text)):
            hit = _checked([mark] + [line for line in row if not _MARK.match(line.text)])
            if not hit:
                continue
            option = compact(hit[0])
            if option.startswith("award"):
                start.append("Award")
            elif option.startswith("noticetoproceed"):
                start.append("Notice to Proceed")
            elif option.startswith("mandatory"):
                period.append("Mandatory")
            elif option.startswith("negotiable"):
                period.append("Negotiable")
            used.extend(hit[1])
        evidence = " ".join(line.text for line in [item11, *sorted(row, key=lambda line: line.x0)])
        source = "11. The Contractor shall begin performance … after receiving"
        emit("contract.performance_start", "Performance Start", source, " / ".join(start), PERFORMANCE, used, evidence)
        emit("contract.performance_period_type", "Performance Period", source, " / ".join(period), PERFORMANCE, used, evidence)

    for field_id, label, marker, pattern in (
        ("contract.offer_due_time", "Offer Due Time", "(hour)", _TIME),
        ("contract.offer_due_date", "Offer Due Date", "(date)", _DATE),
    ):
        anchor = find(marker)
        if not anchor:
            continue
        # The value is typed over the blank just left of / above "(Hour)",
        # either as its own line or inside the "... until 12:00 PM local
        # time 12 Feb 2024" sentence line.
        inline = re.compile(pattern.pattern.replace("^", r"\b").replace("$", r"\b"))
        candidates = []
        for line in lines:
            if not (-14 <= line.y0 - anchor.y0 <= 6) or line.x0 > anchor.x1 + 10:
                continue
            found = list(inline.finditer(line.text))
            if not found:
                continue
            # Inside a sentence line, take the match nearest the anchor's x.
            width = max(line.x1 - line.x0, 1.0)
            per_char = width / max(len(line.text), 1)
            best = min(found, key=lambda m: abs(line.x0 + per_char * (m.start() + m.end()) / 2 - (anchor.x0 + anchor.x1) / 2))
            centre = line.x0 + per_char * (best.start() + best.end()) / 2
            candidates.append((abs(centre - (anchor.x0 + anchor.x1) / 2), best.group(0).strip(), line))
        if candidates:
            _, value, line = min(candidates, key=lambda item: item[0])
            emit(field_id, label, f"local time {marker}", value, PERFORMANCE, [line])

    item13b = find("B. An offer guarantee")
    if item13b:
        row = [line for line in lines if line is not item13b and abs(line.y0 - item13b.y0) <= 4]
        hit = _checked(row)
        if hit:
            answer = "No" if compact(hit[0]).startswith("isnot") else "Yes"
            emit("contract.offer_guarantee_required", "Offer Guarantee Required", "13B. An offer guarantee is / is not required",
                 answer, PERFORMANCE, hit[1], f"{item13b.text} {' '.join(line.text for line in hit[1])}")

    item13d = find("D. Offers providing less than")
    if item13d:
        values = [
            line for line in lines
            if line is not item13d and abs(line.y0 - item13d.y0) <= 4 and line.x0 >= item13d.x0 and _NUMBER.match(line.text.strip())
        ]
        if values:
            value = min(values, key=lambda line: line.x0)
            emit("contract.acceptance_period", "Government Acceptance Period",
                 "13D. Offers providing less than ___ calendar days for Government acceptance",
                 f"{value.text.strip()} calendar days", PERFORMANCE, [value], f"{item13d.text} {value.text}")


# "Label: value" facts printed outside the form boxes (award letters,
# Section A): label pattern -> (canonical id, section, value pattern).
_INLINE_FACTS = (
    (r"\b(UEI|UEID|Unique Entity (ID|Identifier))\b", "contract.uei", CONTRACTOR, r"[A-Z0-9]{12}"),
    (r"\bCAGE( Code)?\b", "contract.cage", CONTRACTOR, r"[A-Z0-9]{5}"),
    (r"\bNAICS\b", "contract.naics", FINANCIAL, r"\d{6}"),
    (r"^Award Date\b", "contract.award_date", SOLICITATION_AWARD, r"\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}[ -][A-Za-z]{3,9}[ -]\d{4}"),
    (r"\bPeriod of Performance\b", "contract.period_of_performance", PERFORMANCE, r".{6,80}"),
    (r"\bPlace of Performance\b", "contract.place_of_performance", PERFORMANCE, r".{4,80}"),
)
_INLINE = re.compile(r"^(?P<label>[^:]{2,90}?)\s*:\s*(?P<value>\S.*)$")


def read_inline_facts(page: PageLines) -> list[ContractField]:
    fields: list[ContractField] = []
    for line in page.lines:
        match = _INLINE.match(line.text.strip())
        if not match:
            continue
        label, value = match.group("label").strip(), match.group("value").strip()
        for label_pattern, field_id, section, value_pattern in _INLINE_FACTS:
            if not re.search(label_pattern, label, re.IGNORECASE):
                continue
            found = re.match(value_pattern, value)
            if found:
                fields.append(
                    ContractField(field_id, label, label, found.group(0).strip(), section, page.page_number,
                                  (line.x0, line.y0, line.x1, line.y1), line.text, "inline_label_value")
                )
            break
    return fields


def read_cover_forms(pages: list[PageLines], max_pages: int = 5) -> list[ContractField]:
    """Every form field on the leading pages (ruled form boxes first, then
    inline "Label: value" facts), first occurrence of a field wins."""
    fields: list[ContractField] = []
    seen: set[str] = set()
    leading = pages[:max_pages]
    for page in leading:
        if is_form_page(page):
            for field in read_form_page(page):
                if field.field_id not in seen:
                    seen.add(field.field_id)
                    fields.append(field)
    for page in leading:
        if is_form_page(page):
            continue
        for field in read_inline_facts(page):
            if field.field_id not in seen:
                seen.add(field.field_id)
                fields.append(field)
    return fields
