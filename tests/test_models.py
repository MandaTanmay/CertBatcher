import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Certificate, Job, JobStatus


@pytest.fixture
def test_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_job_insert(test_db: Session):
    job = Job(
        title="Test Certificate",
        event_name="Test Event",
        issued_by="Test Issuer",
        issue_date=date(2024, 1, 1),
        total_count=5,
    )
    test_db.add(job)
    test_db.commit()
    test_db.refresh(job)

    assert job.id is not None
    assert job.status == JobStatus.PENDING
    assert job.title == "Test Certificate"
    assert job.created_at is not None


def test_certificate_insert(test_db: Session):
    job = Job(
        title="Test Certificate",
        event_name="Test Event",
        issued_by="Test Issuer",
        issue_date=date(2024, 1, 1),
        total_count=1,
    )
    test_db.add(job)
    test_db.commit()
    test_db.refresh(job)

    cert = Certificate(
        job_id=job.id,
        row_index=0,
        recipient_name="John Doe",
        recipient_email="john@example.com",
        raw_data={"name": "John Doe", "email": "john@example.com"},
    )
    test_db.add(cert)
    test_db.commit()
    test_db.refresh(cert)

    assert cert.id is not None
    assert cert.job_id == job.id
    assert cert.row_index == 0
    assert cert.recipient_name == "John Doe"


def test_job_certificates_relationship(test_db: Session):
    job = Job(
        title="Test Certificate",
        event_name="Test Event",
        issued_by="Test Issuer",
        issue_date=date(2024, 1, 1),
        total_count=2,
    )
    test_db.add(job)
    test_db.commit()
    test_db.refresh(job)

    cert1 = Certificate(
        job_id=job.id,
        row_index=0,
        recipient_name="John Doe",
        raw_data={"name": "John Doe"},
    )
    cert2 = Certificate(
        job_id=job.id,
        row_index=1,
        recipient_name="Jane Smith",
        raw_data={"name": "Jane Smith"},
    )
    test_db.add(cert1)
    test_db.add(cert2)
    test_db.commit()

    test_db.refresh(job)
    assert len(job.certificates) == 2
    assert job.certificates[0].recipient_name == "John Doe"
    assert job.certificates[1].recipient_name == "Jane Smith"


def test_unique_job_row_index_constraint(test_db: Session):
    job = Job(
        title="Test Certificate",
        event_name="Test Event",
        issued_by="Test Issuer",
        issue_date=date(2024, 1, 1),
        total_count=2,
    )
    test_db.add(job)
    test_db.commit()
    test_db.refresh(job)

    cert1 = Certificate(
        job_id=job.id,
        row_index=0,
        recipient_name="John Doe",
        raw_data={"name": "John Doe"},
    )
    test_db.add(cert1)
    test_db.commit()

    cert2 = Certificate(
        job_id=job.id,
        row_index=0,
        recipient_name="Jane Smith",
        raw_data={"name": "Jane Smith"},
    )
    test_db.add(cert2)

    with pytest.raises(Exception):
        test_db.commit()



