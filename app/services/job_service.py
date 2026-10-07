from sqlalchemy.orm import Session

from app.models import Certificate, CertStatus, Job, JobStatus
from app.schemas import JobCreateRequest, validate_recipient


def _safe_raw_value(value: object, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:max_length] if value else None


def create_job(db: Session, request: JobCreateRequest) -> Job:
    """
    Create a Job and Certificate records from a bulk request.

    One invalid recipient does not fail the entire job.
    Invalid recipients are stored as FAILED with error_message.
    """
    job = Job(
        title=request.certificate.title,
        event_name=request.certificate.event_name,
        issued_by=request.certificate.issued_by,
        issue_date=request.certificate.issue_date,
        total_count=len(request.recipients),
        field_definitions=[field.model_dump() for field in request.fields],
        status=JobStatus.PENDING,
    )
    try:
        db.add(job)
        db.flush()

        for row_index, raw_recipient in enumerate(request.recipients):
            recipient, error = validate_recipient(raw_recipient, request.fields)

            if recipient:
                certificate = Certificate(
                    job_id=job.id,
                    row_index=row_index,
                    recipient_name=recipient.name,
                    recipient_email=recipient.email,
                    raw_data=(
                        recipient.data
                        if request.fields
                        else raw_recipient
                    ),
                    status=CertStatus.PENDING,
                    error_message=None,
                )
            else:
                certificate = Certificate(
                    job_id=job.id,
                    row_index=row_index,
                    recipient_name=_safe_raw_value(raw_recipient.get("name"), 200),
                    recipient_email=_safe_raw_value(
                        raw_recipient.get("email"), 320
                    ),
                    raw_data=(
                        raw_recipient
                        if not request.fields
                        else (
                            raw_recipient.get("data", {})
                            if isinstance(raw_recipient.get("data", {}), dict)
                            else {}
                        )
                    ),
                    status=CertStatus.FAILED,
                    error_message=error or "Invalid recipient",
                )

            db.add(certificate)

        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def get_certificate_counts(
    db: Session,
    job_id: str,
    total_count: int | None = None,
) -> dict[str, int]:
    certificates = (
        db.query(Certificate.status)
        .filter(Certificate.job_id == job_id)
        .all()
    )
    counts = {
        CertStatus.SUCCESS: 0,
        CertStatus.FAILED: 0,
        CertStatus.PENDING: 0,
    }
    for (certificate_status,) in certificates:
        if certificate_status in counts:
            counts[certificate_status] += 1

    return {
        "total": total_count if total_count is not None else sum(counts.values()),
        "succeeded": counts[CertStatus.SUCCESS],
        "failed": counts[CertStatus.FAILED],
        "pending": counts[CertStatus.PENDING],
    }
