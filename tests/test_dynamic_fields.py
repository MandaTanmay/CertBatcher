from io import BytesIO

from fastapi import status
from pypdf import PdfReader

from app.models import Certificate, Job
from app.schemas import CertificateInfo, FieldDefinition
from app.services.certificate_generator import generate_certificate_pdf


def _payload():
    return {
        "certificate": {
            "title": "Certificate",
            "event_name": "Workshop",
            "issued_by": "Academy",
            "issue_date": "2026-10-01",
        },
        "fields": [
            {"key": "score", "label": "Score", "type": "number", "required": True},
            {"key": "completed_on", "label": "Completed on", "type": "date"},
        ],
        "recipients": [
            {
                "name": "Asha Rao",
                "email": "asha@example.com",
                "data": {"score": "98.5", "completed_on": "2026-09-30"},
            },
            {"name": "Missing Score", "data": {"completed_on": "2026-09-30"}},
        ],
    }


def test_dynamic_fields_are_persisted_and_invalid_rows_are_isolated(
    test_client, test_db
):
    response = test_client.post("/api/jobs/", json=_payload())

    assert response.status_code == status.HTTP_202_ACCEPTED
    job_id = response.json()["id"]
    job = test_db.query(Job).filter(Job.id == job_id).first()
    certificates = (
        test_db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.row_index)
        .all()
    )

    assert job.field_definitions[0]["key"] == "score"
    assert certificates[0].raw_data == {"score": 98.5, "completed_on": "2026-09-30"}
    assert certificates[1].status == "FAILED"
    assert "Score is required" in certificates[1].error_message


def test_dynamic_field_keys_are_unique_and_cannot_replace_core_fields(test_client):
    payload = _payload()
    payload["fields"] = [
        {"key": "name", "label": "Other name", "type": "text"},
        {"key": "name", "label": "Duplicate", "type": "text"},
    ]

    response = test_client.post("/api/jobs/", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_dynamic_values_are_rendered_in_certificate_pdf():
    pdf = generate_certificate_pdf(
        "Alice Johnson",
        CertificateInfo(
            title="Certificate",
            event_name="Workshop",
            issued_by="Academy",
            issue_date="2026-10-01",
        ),
        "certificate-id",
        [FieldDefinition(key="score", label="Score", type="number")],
        {"score": 98.5},
    )

    text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert "Score: 98.5" in text