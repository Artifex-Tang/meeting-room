"""
Pytest configuration.

Test isolation strategy (MySQL, no SQLite):
- session-scoped: create tables in meeting_test once
- function-scoped: DELETE all rows + re-seed between tests
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Must be set before importing app modules
os.environ.setdefault("JWT_SECRET", "test-secret-32bytes-for-pytest-only")

from app.config import settings  # noqa: E402
from app.deps import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

# ── Test DB URL ──────────────────────────────────────────────────────────────
# Replace the last path segment (db name) with meeting_test
_parts = settings.database_url.rsplit("/", 1)
TEST_DATABASE_URL = _parts[0] + "/meeting_test" + (
    "?" + _parts[1].split("?", 1)[1] if "?" in _parts[1] else ""
)

_engine_test = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
_TestSession = sessionmaker(bind=_engine_test, autoflush=False, autocommit=False)


# ── One-time schema setup ────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _setup_schema():
    Base.metadata.create_all(_engine_test)
    yield
    # Leave tables for inspection; CI can drop with a separate job


# ── Per-test DB cleanup ──────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _clean_tables(_setup_schema):
    yield
    with _engine_test.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DELETE FROM `{table.name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


# ── Exposed for concurrency tests ────────────────────────────────────────────
def make_test_session() -> Session:
    """Create a standalone session against meeting_test (for multi-thread tests)."""
    return _TestSession()


# ── Public fixtures ──────────────────────────────────────────────────────────
@pytest.fixture
def db(_clean_tables) -> Session:
    session = _TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db: Session):
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
