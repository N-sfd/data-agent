from sqlalchemy import text
from sqlalchemy.engine import Engine


DOCUMENT_PAGE_COLUMNS: dict[str, str] = {
    "form_fields_json": "JSON",
    "tables_json": "JSON",
    "has_tables": "BOOLEAN NOT NULL DEFAULT 0",
    "has_form_fields": "BOOLEAN NOT NULL DEFAULT 0",
    "is_scanned": "BOOLEAN NOT NULL DEFAULT 0",
    "text_length": "INTEGER NOT NULL DEFAULT 0",
}


def ensure_document_page_columns(engine: Engine) -> None:
    """Add missing document_pages columns for existing SQLite databases."""

    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.execute(
                text("PRAGMA table_info(document_pages)")
            )
        }

        if not existing:
            return

        for column_name, column_type in DOCUMENT_PAGE_COLUMNS.items():
            if column_name in existing:
                continue

            connection.execute(
                text(
                    "ALTER TABLE document_pages "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )
