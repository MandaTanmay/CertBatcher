from datetime import date, datetime, timezone

from app.models import Certificate, CertStatus, JobStatus
from app.schemas import JobCreateRequest
from app.services.job_service import create_job


def _request(names):
    return JobCreateRequest(
        certificate={
            "event_name": "Event",
            "issued_by": "Issuer",
            "issue_date": date(2026, 10, 1),
        },
        recipients=[{"name": name} for name in names],
    )


def test_job_status_returns_progress_counts(test_client, test_db):
    job = create_job(test_db, _request(["One", "Two", "Three"]))
    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id)
        .order_by(Certificate.row_index)
        .all()
    )
    certificates[0].status = CertStatus.SUCCESS
    certificates[1].status = CertStatus.FAILED
    job.status = JobStatus.PROCESSING
    job.started_at = datetime.now(timezone.utc)
    test_db.commit()

    response = test_client.get(f"/api/jobs/{job.id}/")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job.id
    assert data["total"] == 3
    assert data["counts"] == {
        "total": 3,
        "succeeded": 1,
        "failed": 1,
        "pending": 1,
    }
    assert data["started_at"] is not None
    assert data["finished_at"] is None


def test_job_status_returns_job_error(test_client, test_db):
    job = create_job(test_db, _request(["One"]))
    job.status = JobStatus.FAILED
    job.error = "Unexpected processing failure"
    job.finished_at = datetime.now(timezone.utc)
    test_db.commit()

    response = test_client.get(f"/api/jobs/{job.id}/")

    assert response.status_code == 200
    assert response.json()["error"] == "Unexpected processing failure"
    assert response.json()["finished_at"] is not None


def test_unknown_and_invalid_job_ids_return_404(test_client):
    assert test_client.get("/api/jobs/missing/").status_code == 404
    assert test_client.get("/api/jobs/not-a-uuid/").status_code == 404
