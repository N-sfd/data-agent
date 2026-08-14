from dataclasses import dataclass
from pathlib import Path

import fitz


class PDFValidationError(Exception):
    """Raised when an uploaded PDF fails security validation."""


@dataclass(frozen=True)
class PDFMetadata:
    page_count: int
    encrypted: bool
    title: str | None
    author: str | None
    extracted_from_portfolio: bool = False
    embedded_filename: str | None = None


@dataclass(frozen=True)
class EmbeddedPdf:
    filename: str
    data: bytes


def detect_pdf_portfolio(
    document: fitz.Document,
) -> bool:

    first_page_text = ""

    if document.page_count > 0:

        first_page_text = (
            document[0]
            .get_text("text")
            .lower()
        )

    strong_phrases = [
        "pdf portfolio",
        "open this pdf portfolio",
    ]

    return any(
        phrase in first_page_text
        for phrase in strong_phrases
    )


def list_embedded_pdfs(
    document: fitz.Document,
) -> list[EmbeddedPdf]:
    """Return embedded PDF files from a PDF Portfolio / collection."""

    embedded: list[EmbeddedPdf] = []

    try:
        count = document.embfile_count()
    except Exception:
        return embedded

    for index in range(count):
        try:
            info = document.embfile_info(index)
            name = str(
                info.get("filename")
                or info.get("name")
                or f"embedded-{index + 1}.pdf"
            )
            data = document.embfile_get(index)
        except Exception:
            continue

        if not data:
            continue

        lower_name = name.lower()

        looks_like_pdf = (
            lower_name.endswith(".pdf")
            or data[:5] == b"%PDF-"
        )

        if not looks_like_pdf:
            continue

        embedded.append(
            EmbeddedPdf(
                filename=name,
                data=bytes(data),
            )
        )

    return embedded


def extract_primary_embedded_pdf(
    portfolio_path: Path,
    *,
    destination: Path,
) -> EmbeddedPdf:
    """
    Extract the best embedded PDF from a portfolio and write it to destination.

    Prefers the largest embedded PDF, which is usually the real contract.
    """

    pdf: fitz.Document | None = None

    try:
        pdf = fitz.open(portfolio_path)
        embedded = list_embedded_pdfs(pdf)

        if not embedded:
            raise PDFValidationError(
                "This file appears to be a PDF Portfolio, but no "
                "embedded PDF documents were found. Extract or upload "
                "the embedded documents before analysis."
            )

        primary = max(
            embedded,
            key=lambda item: len(item.data),
        )

        destination.write_bytes(primary.data)

        return primary

    finally:
        if pdf is not None:
            pdf.close()


def validate_pdf_structure(
    file_path: Path,
    *,
    max_pages: int,
    allow_encrypted: bool,
) -> PDFMetadata:
    """
    Open a PDF with PyMuPDF and verify its basic structure.

    PDF Portfolios are automatically expanded to their largest
    embedded PDF when possible.
    """

    pdf: fitz.Document | None = None
    extracted_from_portfolio = False
    embedded_filename: str | None = None

    try:
        pdf = fitz.open(file_path)

        if not pdf.is_pdf:
            raise PDFValidationError(
                "The uploaded file is not recognized as a PDF."
            )

        encrypted = bool(pdf.needs_pass)

        if encrypted and not allow_encrypted:
            raise PDFValidationError(
                "Password-protected or encrypted PDFs are not supported."
            )

        if detect_pdf_portfolio(pdf):
            pdf.close()
            pdf = None

            primary = extract_primary_embedded_pdf(
                file_path,
                destination=file_path,
            )

            extracted_from_portfolio = True
            embedded_filename = primary.filename

            pdf = fitz.open(file_path)

            if not pdf.is_pdf or pdf.page_count < 1:
                raise PDFValidationError(
                    "The embedded document extracted from the PDF "
                    "Portfolio could not be opened as a PDF."
                )

        page_count = pdf.page_count

        if page_count < 1:
            raise PDFValidationError(
                "The PDF does not contain any pages."
            )

        if page_count > max_pages:
            raise PDFValidationError(
                f"The PDF contains {page_count} pages. "
                f"The maximum allowed is {max_pages}."
            )

        metadata = pdf.metadata or {}

        return PDFMetadata(
            page_count=page_count,
            encrypted=bool(pdf.needs_pass),
            title=metadata.get("title") or None,
            author=metadata.get("author") or None,
            extracted_from_portfolio=extracted_from_portfolio,
            embedded_filename=embedded_filename,
        )

    except PDFValidationError:
        raise

    except Exception as exc:
        raise PDFValidationError(
            "The PDF is corrupted, malformed, or cannot be opened."
        ) from exc

    finally:
        if pdf is not None:
            pdf.close()
