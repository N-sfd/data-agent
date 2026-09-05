from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {}
engine_kwargs: dict = {}

if settings.database_url.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
    }
else:
    # Managed Postgres (e.g. Render) closes idle connections server-side;
    # pre-ping avoids handing the app a dead connection from the pool.
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(
    settings.resolved_database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
