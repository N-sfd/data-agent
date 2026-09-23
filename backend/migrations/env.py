from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config import get_settings
from app.database.base import Base

# Import every model module for its side effect of registering the
# table with Base.metadata, mirroring the import list in app/main.py.
from app.models import (  # noqa: F401
    classification_audit_log as classification_audit_log_model,
)
from app.models import document as document_model  # noqa: F401
from app.models import extraction_job as extraction_job_model  # noqa: F401
from app.models import document_address as document_address_model  # noqa: F401
from app.models import (  # noqa: F401
    document_amendment_history as document_amendment_history_model,
)
from app.models import document_attachment as document_attachment_model  # noqa: F401
from app.models import document_clause as document_clause_model  # noqa: F401
from app.models import (  # noqa: F401
    document_clause_reference as document_clause_reference_model,
)
from app.models import document_contact as document_contact_model  # noqa: F401
from app.models import (  # noqa: F401
    document_contract_summary as document_contract_summary_model,
)
from app.models import document_qa_review as document_qa_review_model  # noqa: F401
from app.models import far_master_clause as far_master_clause_model  # noqa: F401
from app.models import (  # noqa: F401
    document_delivery_schedule as document_delivery_schedule_model,
)
from app.models import (  # noqa: F401
    document_detected_target as document_detected_target_model,
)
from app.models import (  # noqa: F401
    document_funding_line as document_funding_line_model,
)
from app.models import (  # noqa: F401
    document_insurance_requirement as document_insurance_requirement_model,
)
from app.models import (  # noqa: F401
    document_key_position as document_key_position_model,
)
from app.models import document_line_item as document_line_item_model  # noqa: F401
from app.models import (  # noqa: F401
    document_metadata_field as document_metadata_field_model,
)
from app.models import document_order_range as document_order_range_model  # noqa: F401
from app.models import document_page as document_page_model  # noqa: F401
from app.models import (  # noqa: F401
    document_performance_period as document_performance_period_model,
)
from app.models import (  # noqa: F401
    document_signature as document_signature_model,
)
from app.models import (  # noqa: F401
    document_wawf_instruction as document_wawf_instruction_model,
)
from app.models import (  # noqa: F401
    extraction_model as extraction_model_model,
)
from app.models import (  # noqa: F401
    metadata_field_audit_log as metadata_field_audit_log_model,
)
from app.models import page_text_block as page_text_block_model  # noqa: F401
from app.models import (  # noqa: F401
    relationship_audit_log as relationship_audit_log_model,
)
from app.models import actor as actor_model  # noqa: F401
from app.models import (  # noqa: F401
    document_extracted_table as document_extracted_table_model,
)
from app.models import (  # noqa: F401
    integration_audit_log as integration_audit_log_model,
)
from app.models import (  # noqa: F401
    target_correction as target_correction_model,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use the same resolved database URL the application connects with
# (handles the sqlite relative-path anchor and the postgres:// /
# postgresql+psycopg:// rewrite) instead of the static alembic.ini value.
config.set_main_option(
    "sqlalchemy.url", get_settings().resolved_database_url
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
