from datetime import date
from unittest.mock import patch

from app.models import Certificate, CertStatus, JobStatus
from app.schemas import JobCreateRequest
from app.services.job_service import create_job
from app.services.processor import process_job


def test_failure_isolation_mixed_success_failure(
    test_db, test_storage, test_session_local
):
    """
    Critical test: one certificate failure must NOT prevent others from being processed.
    """
    from app.services.certificate_generator import generate_certificate_pdf

    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[
            {"name": "Asha Rao", "email": "asha@example.com"},
            {"name": "Bad Name"},
            {"name": "Ravi Kumar", "email": "ravi@example.com"},
        ],
    )

    job = create_job(test_db, request)

    def mock_generate(name, info, cert_id):
        if name == "Bad Name":
            raise RuntimeError("boom")
        return generate_certificate_pdf(name, info, cert_id)

    with patch("app.services.processor.SessionLocal", test_session_local):
        with patch(
            "app.services.processor.generate_certificate_pdf", side_effect=mock_generate
        ):
            process_job(job.id)

    test_db.refresh(job)

    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id)
        .order_by(Certificate.row_index)
        .all()
    )

    assert certificates[0].status == CertStatus.SUCCESS
    assert certificates[1].status == CertStatus.FAILED
    assert certificates[2].status == CertStatus.SUCCESS

    assert certificates[1].error_message == "boom"
    assert certificates[1].row_index == 1

    assert job.status == JobStatus.COMPLETED_WITH_ERRORS


def test_all_valid_certificates_become_success(
    test_db, test_storage, test_session_local
):
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[
            {"name": "User 1"},
            {"name": "User 2"},
            {"name": "User 3"},
        ],
    )

    job = create_job(test_db, request)

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    test_db.expire_all()
    test_db.refresh(job)

    certificates = test_db.query(Certificate).filter(Certificate.job_id == job.id).all()

    for cert in certificates:
        assert cert.status == CertStatus.SUCCESS
        assert cert.file_path is not None
        assert cert.generated_at is not None

    assert job.status == JobStatus.COMPLETED


def test_pdf_files_exist_in_storage(test_db, test_storage, test_session_local):
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[{"name": "Test User"}],
    )

    job = create_job(test_db, request)

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    certificates = test_db.query(Certificate).filter(Certificate.job_id == job.id).all()

    for cert in certificates:
        assert cert.file_path is not None
        assert test_storage.exists(cert.file_path)


def test_mixed_success_failure_becomes_completed_with_errors(
    test_db, test_storage, test_session_local
):
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[
            {"name": "Valid User 1"},
            {"name": ""},  # Invalid
            {"name": "Valid User 2"},
        ],
    )

    job = create_job(test_db, request)

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    test_db.refresh(job)

    assert job.status == JobStatus.COMPLETED_WITH_ERRORS


def test_all_invalid_job_becomes_failed(test_db, test_storage, test_session_local):
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[
            {"name": ""},
            {"name": "  "},
        ],
    )

    job = create_job(test_db, request)

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    test_db.refresh(job)

    assert job.status == JobStatus.FAILED


def test_job_started_at_populated(test_db, test_storage, test_session_local):
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[{"name": "User"}],
    )

    job = create_job(test_db, request)
    assert job.started_at is None

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    test_db.refresh(job)
    assert job.started_at is not None


def test_job_finished_at_populated(test_db, test_storage, test_session_local):
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[{"name": "User"}],
    )

    job = create_job(test_db, request)
    assert job.finished_at is None

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    test_db.refresh(job)
    assert job.finished_at is not None


def test_processor_skips_already_failed_certificates(
    test_db, test_storage, test_session_local
):
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[
            {"name": "Valid User"},
            {"name": ""},  # Will be FAILED during creation
        ],
    )

    job = create_job(test_db, request)

    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id)
        .order_by(Certificate.row_index)
        .all()
    )

    assert certificates[0].status == CertStatus.PENDING
    assert certificates[1].status == CertStatus.FAILED

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    test_db.expire_all()
    test_db.refresh(job)
    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id)
        .order_by(Certificate.row_index)
        .all()
    )

    assert certificates[0].status == CertStatus.SUCCESS
    assert certificates[1].status == CertStatus.FAILED  # Still FAILED, not reprocessed


def test_processor_does_not_process_twice(test_db, test_storage, test_session_local):
    request = JobCreateRequest(
        certificate={
            "title": "Certificate",
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[{"name": "User"}],
    )

    job = create_job(test_db, request)

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    test_db.refresh(job)
    assert job.status == JobStatus.COMPLETED

    with patch("app.services.processor.SessionLocal", test_session_local):
        process_job(job.id)

    test_db.refresh(job)
    assert job.status == JobStatus.COMPLETED  # Still COMPLETED, not changed
