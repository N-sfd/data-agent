from docx import Document


def parse_docx(file_path: str) -> dict:
    document = Document(file_path)

    paragraphs = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    tables = []

    for table in document.tables:
        rows = []

        for row in table.rows:
            rows.append([cell.text.strip() for cell in row.cells])

        tables.append(rows)

    return {
        "paragraphs": paragraphs,
        "tables": tables,
    }
