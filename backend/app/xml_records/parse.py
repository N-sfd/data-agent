"""XML → records, schema-neutral.

The repeating element that carries the data (e.g. every <Clause> of a
clause-library file) becomes one record per element. Its child elements and
attributes become the columns, captioned from the file's own tag names
("ProvisionYn" → "Provision Yn"); nothing is renamed to a target schema.
Paragraph markup inside a value (<Text><p>…</p><p>…</p></Text>) stays
together as one text, one line per paragraph. Values outside any record are
document details. Every value keeps the element path it came from.

Parsing is hardened: no entity expansion, no DTD loading, no network access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

from app.staging.labels import humanize_label


class XmlSourceError(ValueError):
    """The file is not well-formed XML, or uses constructs we refuse."""


# Markup that formats text rather than structuring data: an element whose
# descendants are all of these is read as one text value.
TEXT_MARKUP = frozenset(
    {
        "p", "para", "br", "b", "i", "u", "em", "strong", "span", "sub", "sup", "a", "div",
        "li", "ul", "ol", "dl", "dt", "dd", "table", "thead", "tbody", "tr", "td", "th",
        "font", "small", "big", "code", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
        "hr", "s", "strike", "cite", "q", "abbr", "caption", "col", "colgroup", "center",
    }
)
# Nested structure deeper than this is read as text.
_MAX_DEPTH = 3
MAX_GROUPS = 4
MAX_COLUMNS = 150


@dataclass
class XmlValue:
    key: str  # stable within the file: the tag path inside the record
    label: str  # caption from the file's own tag names
    value: str
    path: str  # absolute element path, e.g. /Clauses/Clause[3]/Title


@dataclass
class XmlRecord:
    path: str
    values: dict[str, XmlValue] = field(default_factory=dict)


@dataclass
class XmlRecordGroup:
    tag: str
    label: str  # "Clauses"
    path: str  # "/ClauseLibrary/Clause"
    columns: list[tuple[str, str]] = field(default_factory=list)  # (key, label), first-seen order
    records: list[XmlRecord] = field(default_factory=list)
    dropped_columns: int = 0


@dataclass
class XmlDocument:
    root_tag: str
    root_label: str
    details: list[XmlValue] = field(default_factory=list)
    groups: list[XmlRecordGroup] = field(default_factory=list)
    element_count: int = 0


def _local(element) -> str:
    return etree.QName(element).localname


# Words a single-case compound tag ("datepublished", "STARTDATE") may be
# made of. A compound is split only when every part is one of these, so a
# real word ("description") is never cut apart.
_TAG_WORDS = frozenset(
    """
    date published start end effective expiration due issue issued display name clause type status text
    title number lock global provision insert by reference attribute category language intent description
    version source file id code amount total sub tax rate unit price quantity line item invoice order
    purchase vendor supplier customer contract award period from to value currency created updated
    modified last first effective owner org organization address city state zip postal country phone
    email contact
    """.split()
)


def _split_compound(word: str) -> list[str] | None:
    """'datepublished' -> ['date', 'published'] when every part is a known
    word (at least two parts); None otherwise."""

    lower = word.lower()
    if lower in _TAG_WORDS or len(lower) < 6:
        return None
    best: dict[int, list[str]] = {0: []}
    for end in range(1, len(lower) + 1):
        for start in range(max(0, end - 14), end):
            if start in best and lower[start:end] in _TAG_WORDS:
                candidate = best[start] + [lower[start:end]]
                if end not in best or len(candidate) < len(best[end]):
                    best[end] = candidate
    parts = best.get(len(lower))
    return parts if parts and len(parts) >= 2 else None


def tag_label(tag: str) -> str:
    """'ProvisionYn' → 'Provision Yn'; 'DATE_PUBLISHED' → 'Date Published';
    'Attribute1' → 'Attribute 1'; 'XMLFileName' → 'XML File Name';
    'datepublished' → 'Date Published' (known words only)."""

    if tag.isalpha() and (tag.islower() or tag.isupper()):
        parts = _split_compound(tag)
        if parts:
            return " ".join(part.title() for part in parts)
    text = re.sub(r"[_\-.:]+", " ", tag)
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", text)
    return humanize_label(text) or tag


def plural(label: str) -> str:
    if re.search(r"(s|x|ch|sh)$", label, re.I):
        return label if label.lower().endswith("s") else f"{label}es"
    if re.search(r"[^aeiou]y$", label, re.I):
        return f"{label[:-1]}ies"
    return f"{label}s"


def parse_tree(raw: bytes):
    # Entity declarations are refused outright (entity-expansion attacks);
    # the parser additionally never resolves entities, loads DTDs or
    # touches the network.
    if re.search(rb"<!ENTITY", raw[:200_000], re.I):
        raise XmlSourceError("XML entity declarations are not accepted.")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        remove_comments=True,
        remove_pis=True,
        huge_tree=False,
    )
    try:
        return etree.fromstring(raw, parser)
    except etree.XMLSyntaxError as exc:
        raise XmlSourceError(f"The file is not well-formed XML: {exc}") from exc


def _clean(text: str | None) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", text or "").strip()


def _is_text(element) -> bool:
    return all(_local(child).lower() in TEXT_MARKUP for child in element.iterdescendants() if isinstance(child.tag, str))


def text_of(element) -> str:
    """The element's text. Mixed content reads inline; element-only
    content puts each child on its own line (paragraphs stay together)."""

    children = [c for c in element if isinstance(c.tag, str)]
    if not children:
        return _clean(element.text)
    mixed = _clean(element.text) or any(_clean(c.tail) for c in children)
    if mixed:
        return _clean(" ".join(element.itertext()))
    lines = [text_of(child) for child in children]
    return "\n".join(line for line in lines if line)


def _paths(root) -> dict:
    """Absolute path per element, with sibling positions where a tag repeats."""

    paths = {root: f"/{_local(root)}"}
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        counts: dict[str, int] = {}
        children = [c for c in element if isinstance(c.tag, str)]
        totals: dict[str, int] = {}
        for child in children:
            totals[_local(child)] = totals.get(_local(child), 0) + 1
        for child in children:
            name = _local(child)
            counts[name] = counts.get(name, 0) + 1
            suffix = f"[{counts[name]}]" if totals[name] > 1 else ""
            paths[child] = f"{paths[element]}/{name}{suffix}"
    return paths


def _signature(element) -> tuple[str, ...]:
    names = [_local(element)]
    for ancestor in element.iterancestors():
        names.append(_local(ancestor))
    return tuple(reversed(names))


def _record_groups(root) -> list[tuple[tuple[str, ...], list]]:
    """Repeating, structured elements, best first, none nested in another."""

    by_signature: dict[tuple[str, ...], list] = {}
    for element in root.iter():
        if not isinstance(element.tag, str) or element is root:
            continue
        if not any(isinstance(c.tag, str) for c in element) and not element.attrib:
            continue
        if _local(element).lower() in TEXT_MARKUP:
            continue
        by_signature.setdefault(_signature(element), []).append(element)

    candidates = []
    for signature, elements in by_signature.items():
        if len(elements) < 2:
            continue
        fields = {_local(c) for e in elements for c in e if isinstance(c.tag, str)} | {
            a for e in elements for a in e.attrib
        }
        if len(fields) < 2 and not all(_is_text(e) for e in elements):
            continue
        candidates.append((len(elements) * max(len(fields), 1), signature, elements))
    candidates.sort(key=lambda item: -item[0])

    chosen: list[tuple[tuple[str, ...], list]] = []
    for _score, signature, elements in candidates:
        if any(signature[: len(s)] == s or s[: len(signature)] == signature for s, _ in chosen):
            continue
        chosen.append((signature, elements))
        if len(chosen) == MAX_GROUPS:
            break
    # Document order.
    order = {element: index for index, element in enumerate(root.iter())}
    return sorted(chosen, key=lambda item: order[item[1][0]])


def _record_values(element, paths, prefix: tuple[str, ...] = (), depth: int = 0) -> list[XmlValue]:
    values: list[XmlValue] = []
    for name, value in element.attrib.items():
        local = etree.QName(name).localname
        key = "/".join(prefix + (f"@{local}",))
        label = " ".join([tag_label(p) for p in prefix] + [tag_label(local)])
        if _clean(value):
            values.append(XmlValue(key, label, _clean(value), f"{paths[element]}/@{local}"))
    children = [c for c in element if isinstance(c.tag, str)]
    totals: dict[str, int] = {}
    for child in children:
        totals[_local(child)] = totals.get(_local(child), 0) + 1
    grouped: dict[str, list] = {}
    for child in children:
        grouped.setdefault(_local(child), []).append(child)
    for name, items in grouped.items():
        key_parts = prefix + (name,)
        label = " ".join(tag_label(p) for p in key_parts)
        structured = (
            len(items) == 1
            and depth < _MAX_DEPTH
            and any(isinstance(c.tag, str) for c in items[0])
            and not _is_text(items[0])
            and not _clean(items[0].text)
        )
        if structured:
            values += _record_values(items[0], paths, key_parts, depth + 1)
            continue
        texts = [text_of(item) for item in items]
        joined = "\n".join(t for t in texts if t)
        if joined:
            values.append(XmlValue("/".join(key_parts), label, joined, paths[items[0]]))
        # Attributes of repeated elements: one line per element, in order.
        attributes: dict[str, list[str]] = {}
        for item in items:
            for attr, value in item.attrib.items():
                attributes.setdefault(etree.QName(attr).localname, []).append(_clean(value))
        for local, found in attributes.items():
            joined_attr = "\n".join(v for v in found if v)
            if joined_attr:
                values.append(
                    XmlValue(
                        "/".join(key_parts + (f"@{local}",)),
                        f"{label} {tag_label(local)}",
                        joined_attr,
                        f"{paths[items[0]]}/@{local}",
                    )
                )
    if not children and not element.attrib and _clean(element.text):
        values.append(XmlValue("/".join(prefix) or "value", " ".join(tag_label(p) for p in prefix) or "Value", _clean(element.text), paths[element]))
    elif children == [] and _clean(element.text) and element.attrib:
        values.append(XmlValue("/".join(prefix + ("#text",)), " ".join(tag_label(p) for p in prefix) or "Value", _clean(element.text), paths[element]))
    return values


def parse_xml(raw: bytes) -> XmlDocument:
    root = parse_tree(raw)
    paths = _paths(root)
    # A root name like OKCXMLIMPDFN is an identifier: kept as printed.
    document = XmlDocument(root_tag=_local(root), root_label=_local(root) if _local(root).isupper() else tag_label(_local(root)))
    document.element_count = sum(1 for e in root.iter() if isinstance(e.tag, str))

    inside: set = set()
    used_labels: dict[str, int] = {}
    for signature, elements in _record_groups(root):
        tag = signature[-1]
        label = plural(tag_label(tag))
        used_labels[label] = used_labels.get(label, 0) + 1
        if used_labels[label] > 1:
            label = f"{label} ({' '.join(tag_label(s) for s in signature[-2:-1])})"
        group = XmlRecordGroup(tag=tag, label=label, path="/" + "/".join(signature))
        seen: dict[str, str] = {}
        for element in elements:
            inside.update(element.iter())
            record = XmlRecord(path=paths[element])
            for value in _record_values(element, paths):
                if value.key not in seen:
                    if len(seen) >= MAX_COLUMNS:
                        group.dropped_columns += 1
                        continue
                    seen[value.key] = value.label
                record.values[value.key] = value
            group.records.append(record)
        group.columns = list(seen.items())
        # Two keys may humanize alike ("Title" and "TITLE"): keep both, apart.
        counts: dict[str, int] = {}
        for index, (key, column_label) in enumerate(group.columns):
            counts[column_label] = counts.get(column_label, 0) + 1
            if counts[column_label] > 1:
                group.columns[index] = (key, f"{column_label} ({key})")
        document.groups.append(group)

    def attributes(element) -> None:
        for name, value in element.attrib.items():
            local = etree.QName(name).localname
            if _clean(value):
                caption = tag_label(local) if element is root else f"{tag_label(_local(element))} {tag_label(local)}"
                path = f"{paths[element]}/@{local}"
                document.details.append(XmlValue(path, caption, _clean(value), path))

    def details(element) -> None:
        # Values outside every record; a text element is one value.
        attributes(element)
        for child in element:
            if not isinstance(child.tag, str) or child in inside:
                continue
            if any(isinstance(c.tag, str) for c in child) and not _is_text(child):
                details(child)
                continue
            attributes(child)
            text = text_of(child)
            if text:
                document.details.append(XmlValue(paths[child], tag_label(_local(child)), text, paths[child]))

    details(root)
    return document


def readable_text(raw: bytes) -> str:
    """The Source/Transcription view of an XML file: one 'Label: value'
    line per value, records separated by their element path."""

    document = parse_xml(raw)
    lines: list[str] = [document.root_label, ""]
    for value in document.details:
        lines.append(f"{value.label}: {value.value}")
    for group in document.groups:
        lines += ["", f"{group.label} ({len(group.records)})"]
        for record in group.records:
            lines += ["", record.path]
            for value in record.values.values():
                lines.append(f"{value.label}: {value.value}")
    return "\n".join(lines).strip() + "\n"
