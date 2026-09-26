"""Detects source files whose visible pages are not the real content, so
Results can explain the condition instead of showing an empty workbook.

The motivating case is an Adobe PDF Portfolio (reference/regression/
Contract.pdf): a one-page "open this portfolio in Acrobat" placeholder whose
actual documents live as embedded files. Every page-based extractor
correctly finds nothing on that placeholder page, which is indistinguishable
from "no supported fields" unless the condition is detected here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

SOURCE_KIND_STANDARD = "standard"
SOURCE_KIND_PDF_PORTFOLIO = "pdf_portfolio"
SOURCE_KIND_PDF_EMBEDDED_FILES = "pdf_with_embedded_files"


@dataclass
class EmbeddedFile:
    name: str
    size_bytes: int | None = None


@dataclass
class SourceInspection:
    kind: str = SOURCE_KIND_STANDARD
    embedded_files: list[EmbeddedFile] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _is_portfolio(fitz_doc) -> bool:
    # A portfolio is declared by a /Collection entry in the document catalog
    # (ISO 32000-1 §12.3.5), not by the mere presence of attachments.
    try:
        catalog_xref = fitz_doc.pdf_catalog()
        if not catalog_xref:
            return False
        key_type, _ = fitz_doc.xref_get_key(catalog_xref, "Collection")
        return key_type != "null"
    except Exception:  # noqa: BLE001 - malformed catalog: treat as standard
        return False


def _embedded_files(fitz_doc) -> list[EmbeddedFile]:
    files: list[EmbeddedFile] = []
    try:
        count = fitz_doc.embfile_count()
    except Exception:  # noqa: BLE001
        return files
    for index in range(count):
        try:
            info = fitz_doc.embfile_info(index)
        except Exception:  # noqa: BLE001
            continue
        name = info.get("filename") or info.get("name") or f"embedded-{index + 1}"
        size = info.get("size")
        files.append(
            EmbeddedFile(name=str(name), size_bytes=int(size) if size is not None else None)
        )
    return files


def inspect_pdf(fitz_doc) -> SourceInspection:
    """`fitz_doc` is an already-open PyMuPDF document; it is not closed here."""

    embedded = _embedded_files(fitz_doc)
    if _is_portfolio(fitz_doc):
        return SourceInspection(kind=SOURCE_KIND_PDF_PORTFOLIO, embedded_files=embedded)
    if embedded:
        return SourceInspection(kind=SOURCE_KIND_PDF_EMBEDDED_FILES, embedded_files=embedded)
    return SourceInspection()
