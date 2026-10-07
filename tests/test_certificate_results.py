from datetime import date

from app.models import Certificate, CertStatus
from app.schemas import JobCreateRequest
from app.services.job_service import create_job


def test_certificate_results_are_sorted_and_include_status_data(
    test_client, test_db
):
    job = create_job(
        test_db,
        JobCreateRequest(
            certificate={
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": date(2026, 10, 1),
            },
            recipients=[
                {"name": "First", "email": "first@example.com"},
                {"name": ""},
                {"name": "Third"},
            ],
        ),
    )
    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id)
        .order_by(Certificate.row_index)
        .all()
    )
    certificates[2].status = CertStatus.SUCCESS
    certificates[2].file_path = f"{job.id}/{certificates[2].id}.pdf"
    test_db.commit()

    response = test_client.get(f"/api/jobs/{job.id}/certificates/")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job.id
    assert [item["row_index"] for item in data["items"]] == [0, 1, 2]
    assert data["items"][0]["status"] == CertStatus.PENDING
    assert data["items"][1]["status"] == CertStatus.FAILED
    assert data["items"][1]["error_message"]
    assert data["items"][2]["file_path"].endswith(".pdf")


def test_certificate_results_do_not_cross_job_boundaries(test_client, test_db):
    first = create_job(
        test_db,
        JobCreateRequest(
            certificate={
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": date(2026, 10, 1),
            },
            recipients=[{"name": "First"}],
        ),
    )
    second = create_job(
        test_db,
        JobCreateRequest(
            certificate={
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": date(2026, 10, 1),
            },
            recipients=[{"name": "Second"}],
        ),
    )

    response = test_client.get(f"/api/jobs/{first.id}/certificates/")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["recipient_name"] == "First"
    assert response.json()["items"][0]["recipient_name"] != second.title


def test_unknown_job_certificate_results_return_404(test_client):
    response = test_client.get("/api/jobs/missing/certificates/")

    assert response.status_code == 404
