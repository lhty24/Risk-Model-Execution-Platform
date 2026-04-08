import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://mex:mex_dev@localhost:5432/mex")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, closing it when done."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
