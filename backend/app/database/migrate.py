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


DOCUMENT_METADATA_FIELD_COLUMNS: dict[str, str] = {
    "human_approved": "BOOLEAN NOT NULL DEFAULT 0",
    "review_status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
    "original_value": "TEXT NOT NULL DEFAULT ''",
}


DOCUMENT_COLUMNS: dict[str, str] = {
    "document_type": "VARCHAR(60)",
    "industry": "VARCHAR(60)",
    "contract_side": "VARCHAR(20)",
    "document_language": "VARCHAR(40)",
    "classification_confidence": "FLOAT",
    "parent_document_id": "VARCHAR(36)",
    "parent_relationship_type": "VARCHAR(30)",
    "parent_relationship_confidence": "FLOAT",
    "parent_relationship_matched_on": "VARCHAR(20)",
    "parent_relationship_status": "VARCHAR(20)",
    "processing_duration_seconds": "FLOAT",
    "approved_by": "VARCHAR(120)",
    "approved_at": "DATETIME",
    "document_status": "VARCHAR(30)",
    "parent_relationship_reasons": "JSON",
    "parent_relationship_detection_method": "VARCHAR(20)",
    "promoted_by": "VARCHAR(120)",
    "promoted_at": "DATETIME",
    "organization_id": "VARCHAR(36)",
    "owner_id": "VARCHAR(36)",
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


def ensure_documents_columns(engine: Engine) -> None:
    """Add missing documents columns for existing SQLite databases."""

    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.execute(
                text("PRAGMA table_info(documents)")
            )
        }

        if not existing:
            return

        for column_name, column_type in DOCUMENT_COLUMNS.items():
            if column_name in existing:
                continue

            connection.execute(
                text(
                    "ALTER TABLE documents "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )


def ensure_document_metadata_field_columns(engine: Engine) -> None:
    """
    Add missing document_metadata_fields columns for existing
    SQLite databases.
    """

    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.execute(
                text(
                    "PRAGMA table_info(document_metadata_fields)"
                )
            )
        }

        if not existing:
            return

        for (
            column_name,
            column_type,
        ) in DOCUMENT_METADATA_FIELD_COLUMNS.items():
            if column_name in existing:
                continue

            connection.execute(
                text(
                    "ALTER TABLE document_metadata_fields "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )
