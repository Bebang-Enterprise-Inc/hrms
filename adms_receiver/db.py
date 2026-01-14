from __future__ import annotations

import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker


def make_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def wait_for_db(engine, *, timeout_seconds: int = 60, sleep_seconds: float = 2.0) -> None:
    """Block until the DB is reachable (or raise after timeout)."""
    deadline = time.time() + float(timeout_seconds)
    last_err: Exception | None = None

    while time.time() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as e:
            last_err = e
            time.sleep(sleep_seconds)

    raise RuntimeError(f"DB not reachable after {timeout_seconds}s") from last_err
