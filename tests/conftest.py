from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_storage
from app.main import app
from app.schemas import CertificateInfo

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(test_engine):
    session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_storage(tmp_path, monkeypatch):
    from app.services.storage import FileSystemStorage

    storage = FileSystemStorage(tmp_path)
    monkeypatch.setattr("app.services.processor.get_storage", lambda: storage)
    return storage


@pytest.fixture
def test_client(test_db, test_storage, test_session_local):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_get_storage():
        return test_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage

    with patch("app.api.jobs.process_job"), patch(
        "app.services.processor.SessionLocal", test_session_local
    ), patch(
        "app.services.processor.get_storage",
        return_value=test_storage,
    ):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_certificate_info():
    return CertificateInfo(
        title="Certificate of Completion",
        event_name="Python Bootcamp 2026",
        issued_by="ABC Academy",
        issue_date=date(2026, 10, 1),
    )


@pytest.fixture
def test_session_local(test_engine):
    """Provide a SessionLocal factory for processor tests."""
    session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def factory():
        return session_factory()

    return factory
