from fastapi import status

from app.models import Certificate, CertStatus, Job, JobStatus


def test_valid_payload_returns_202(test_client):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate of Completion",
                "event_name": "Python Bootcamp 2026",
                "issued_by": "ABC Academy",
                "issue_date": "2026-10-01",
            },
            "recipients": [
                {"name": "Asha Rao", "email": "asha@example.com"},
                {"name": "Ravi Kumar"},
            ],
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert "id" in data
    assert data["status"] == "PENDING"
    assert data["total"] == 2
    assert "status_url" in data


def test_response_contains_required_fields(test_client):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [{"name": "Test User"}],
        },
    )

    data = response.json()
    assert "id" in data
    assert data["status"] == "PENDING"
    assert data["total"] == 1
    assert data["status_url"].startswith("/api/jobs/")
    assert data["status_url"].endswith("/")


def test_database_contains_one_job(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [{"name": "Test User"}],
        },
    )

    job_id = response.json()["id"]
    job = test_db.query(Job).filter(Job.id == job_id).first()

    assert job is not None
    assert job.status == JobStatus.PENDING
    assert job.total_count == 1


def test_database_contains_n_certificate_rows(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [
                {"name": "User 1"},
                {"name": "User 2"},
                {"name": "User 3"},
            ],
        },
    )

    job_id = response.json()["id"]
    certificates = test_db.query(Certificate).filter(Certificate.job_id == job_id).all()

    assert len(certificates) == 3


def test_certificate_row_index_values_correct(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [
                {"name": "User 1"},
                {"name": "User 2"},
                {"name": "User 3"},
            ],
        },
    )

    job_id = response.json()["id"]
    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.row_index)
        .all()
    )

    assert certificates[0].row_index == 0
    assert certificates[1].row_index == 1
    assert certificates[2].row_index == 2


def test_valid_recipient_rows_initially_pending(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [
                {"name": "Valid User 1", "email": "user1@example.com"},
                {"name": "Valid User 2"},
            ],
        },
    )

    job_id = response.json()["id"]
    certificates = test_db.query(Certificate).filter(Certificate.job_id == job_id).all()

    for cert in certificates:
        assert cert.status == CertStatus.PENDING
        assert cert.error_message is None


def test_invalid_recipient_rows_become_failed(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [
                {"name": "Valid User"},
                {"name": ""},
                {"name": "  "},
            ],
        },
    )

    job_id = response.json()["id"]
    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.row_index)
        .all()
    )

    assert certificates[0].status == CertStatus.PENDING
    assert certificates[1].status == CertStatus.FAILED
    assert certificates[2].status == CertStatus.FAILED


def test_invalid_row_contains_error_message(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [{"name": ""}],
        },
    )

    job_id = response.json()["id"]
    cert = test_db.query(Certificate).filter(Certificate.job_id == job_id).first()

    assert cert.status == CertStatus.FAILED
    assert cert.error_message is not None
    assert "Name cannot be blank" in cert.error_message


def test_raw_data_preserves_original_recipient_data(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [
                {"name": "User", "email": "user@example.com", "extra_field": "ignored"}
            ],
        },
    )

    job_id = response.json()["id"]
    cert = test_db.query(Certificate).filter(Certificate.job_id == job_id).first()

    assert cert.raw_data == {
        "name": "User",
        "email": "user@example.com",
        "extra_field": "ignored",
    }


def test_empty_recipients_returns_422(test_client):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_missing_certificate_returns_422(test_client):
    response = test_client.post(
        "/api/jobs/",
        json={
            "recipients": [{"name": "User"}],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_invalid_certificate_date_returns_422(test_client):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "invalid-date",
            },
            "recipients": [{"name": "User"}],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_too_many_recipients_returns_422(test_client):
    recipients = [{"name": f"User {i}"} for i in range(1001)]

    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": recipients,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Too many recipients" in response.json()["detail"]


def test_unknown_fields_do_not_crash_valid_requests(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
                "unknown_field": "ignored",
            },
            "recipients": [
                {"name": "User", "email": "user@example.com", "extra": "data"}
            ],
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED

    job_id = response.json()["id"]
    cert = test_db.query(Certificate).filter(Certificate.job_id == job_id).first()

    assert cert.raw_data == {
        "name": "User",
        "email": "user@example.com",
        "extra": "data",
    }


def test_multiple_recipients_accepted_in_one_request(test_client, test_db):
    response = test_client.post(
        "/api/jobs/",
        json={
            "certificate": {
                "title": "Certificate",
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": "2026-10-01",
            },
            "recipients": [
                {"name": "User 1"},
                {"name": "User 2"},
                {"name": "User 3"},
                {"name": "User 4"},
                {"name": "User 5"},
            ],
        },
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["total"] == 5

    job_id = response.json()["id"]
    certificates = test_db.query(Certificate).filter(Certificate.job_id == job_id).all()

    assert len(certificates) == 5
