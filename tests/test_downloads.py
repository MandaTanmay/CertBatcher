from datetime import date
from io import BytesIO
from zipfile import ZipFile

from app.models import Certificate, CertStatus
from app.schemas import JobCreateRequest
from app.services.job_service import create_job


def _create_job(test_db):
    return create_job(
        test_db,
        JobCreateRequest(
            certificate={
                "event_name": "Event",
                "issued_by": "Issuer",
                "issue_date": date(2026, 10, 1),
            },
            recipients=[{"name": "First"}, {"name": "Second"}, {"name": ""}],
        ),
    )


def _store_success(test_db, test_storage, job, certificate, content=b"%PDF-test"):
    certificate.status = CertStatus.SUCCESS
    certificate.file_path = test_storage.save(job.id, certificate.id, content)
    test_db.commit()


def test_pdf_download_returns_generated_file(test_client, test_db, test_storage):
    job = _create_job(test_db)
    certificate = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id, Certificate.row_index == 0)
        .one()
    )
    _store_success(test_db, test_storage, job, certificate)

    response = test_client.get(
        f"/api/jobs/{job.id}/certificates/{certificate.id}/download"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content == b"%PDF-test"
    assert (
        f"certificate-{certificate.id}.pdf"
        in response.headers["content-disposition"]
    )


def test_pdf_download_rejects_missing_and_failed_files(
    test_client, test_db, test_storage
):
    job = _create_job(test_db)
    failed = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id, Certificate.row_index == 2)
        .one()
    )
    assert test_client.get(
        f"/api/jobs/{job.id}/certificates/{failed.id}/download"
    ).status_code == 409
    assert test_client.get(
        f"/api/jobs/{job.id}/certificates/missing/download"
    ).status_code == 404
    assert test_client.get(
        "/api/jobs/missing/certificates/missing/download"
    ).status_code == 404

    pending = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id, Certificate.row_index == 0)
        .one()
    )
    pending.status = CertStatus.SUCCESS
    pending.file_path = "missing/file.pdf"
    test_db.commit()
    assert test_client.get(
        f"/api/jobs/{job.id}/certificates/{pending.id}/download"
    ).status_code == 404


def test_pdf_download_rejects_certificate_from_another_job(
    test_client, test_db, test_storage
):
    first = _create_job(test_db)
    second = _create_job(test_db)
    certificate = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == second.id, Certificate.row_index == 0)
        .one()
    )
    _store_success(test_db, test_storage, second, certificate)

    response = test_client.get(
        f"/api/jobs/{first.id}/certificates/{certificate.id}/download"
    )

    assert response.status_code == 404


def test_zip_download_contains_only_available_successes(
    test_client, test_db, test_storage
):
    job = _create_job(test_db)
    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job.id)
        .order_by(Certificate.row_index)
        .all()
    )
    _store_success(test_db, test_storage, job, certificates[0], b"first")
    _store_success(test_db, test_storage, job, certificates[1], b"second")

    response = test_client.get(f"/api/jobs/{job.id}/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == [
            f"certificate-{certificates[0].id}.pdf",
            f"certificate-{certificates[1].id}.pdf",
        ]
        assert archive.read(archive.namelist()[0]) == b"first"


def test_zip_download_requires_a_generated_certificate(test_client, test_db):
    job = _create_job(test_db)

    response = test_client.get(f"/api/jobs/{job.id}/download")

    assert response.status_code == 409
    assert response.json()["detail"] == "No generated certificates available"
    assert test_client.get("/api/jobs/missing/download").status_code == 404
