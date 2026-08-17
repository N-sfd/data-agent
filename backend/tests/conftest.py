import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.migrate import (  # noqa: E402
    ensure_document_metadata_field_columns,
    ensure_document_page_columns,
    ensure_documents_columns,
)
from app.database.session import engine  # noqa: E402
from app.models import document as _document_model  # noqa: E402,F401
from app.models import (  # noqa: E402,F401
    document_clause as _document_clause_model,
)
from app.models import (  # noqa: E402,F401
    document_metadata_field as _document_metadata_field_model,
)
from app.models import document_page as _document_page_model  # noqa: E402,F401
from app.models import (  # noqa: E402,F401
    document_signature as _document_signature_model,
)
from app.models import (  # noqa: E402,F401
    extraction_model as _extraction_model_model,
)
from app.models import (  # noqa: E402,F401
    metadata_field_audit_log as _metadata_field_audit_log_model,
)
from app.models import (  # noqa: E402,F401
    page_text_block as _page_text_block_model,
)


@pytest.fixture(scope="session", autouse=True)
def _initialize_database() -> None:
    """
    FastAPI's `@app.on_event("startup")` handler (which normally runs
    this same migration) does not fire for a plain, non-context-managed
    `TestClient(app)` — every test file in this suite instantiates the
    client that way. Without this, the test DB silently keeps whatever
    stale schema it already had, which only "worked" before because a
    manually-run `uvicorn` dev server happened to migrate the shared
    SQLite file first. Running the same migration helpers eagerly here
    guarantees the schema is correct before any test runs, regardless
    of how the app is invoked.
    """

    Base.metadata.create_all(bind=engine)
    ensure_document_page_columns(engine)
    ensure_documents_columns(engine)
    ensure_document_metadata_field_columns(engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
