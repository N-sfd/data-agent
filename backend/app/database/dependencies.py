from collections.abc import Generator

from sqlalchemy.orm import Session

from app.database.session import SessionLocal


def get_database() -> Generator[Session, None, None]:
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()
