import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.dependencies import get_storage
from app.models import Certificate, CertStatus, Job, JobStatus
from app.schemas import CertificateInfo, FieldDefinition
from app.services.certificate_generator import generate_certificate_pdf

logger = logging.getLogger(__name__)


def process_job(job_id: str) -> None:
    """
    Process a job: generate PDFs for all pending certificates.

    Creates its own database session for background processing.
    Isolates individual certificate failures.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            logger.warning("Job %s not found", job_id)
            return

        if job.status in {
            JobStatus.COMPLETED,
            JobStatus.COMPLETED_WITH_ERRORS,
            JobStatus.FAILED,
        }:
            return

        storage = get_storage()
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        pending_certificates = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job_id,
                Certificate.status == CertStatus.PENDING,
            )
            .all()
        )

        cert_info = CertificateInfo(
            title=job.title,
            event_name=job.event_name,
            issued_by=job.issued_by,
            issue_date=job.issue_date,
        )
        fields = [
            FieldDefinition.model_validate(field)
            for field in job.field_definitions or []
        ]

        for cert in pending_certificates:
            try:
                if fields:
                    pdf_bytes = generate_certificate_pdf(
                        cert.recipient_name or "Unknown",
                        cert_info,
                        cert.id,
                        fields,
                        cert.raw_data or {},
                    )
                else:
                    pdf_bytes = generate_certificate_pdf(
                        cert.recipient_name or "Unknown",
                        cert_info,
                        cert.id,
                    )

                file_path = storage.save(job.id, cert.id, pdf_bytes)

                cert.status = CertStatus.SUCCESS
                cert.file_path = file_path
                cert.generated_at = datetime.now(timezone.utc)
                db.commit()

            except Exception as exc:
                logger.error(
                    f"Failed to process certificate {cert.id}: {exc}",
                    exc_info=True,
                )
                cert.status = CertStatus.FAILED
                cert.error_message = str(exc)
                db.commit()
                continue

        _finalize_job(db, job)

    except Exception as exc:
        logger.error("Job-level failure for %s", job_id, exc_info=True)

        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as rollback_exc:
            logger.error(f"Failed to mark job as failed: {rollback_exc}")
    finally:
        db.close()


def _finalize_job(db: Session, job: Job) -> None:
    """
    Determine final job status based on certificate outcomes.
    """
    certificates = db.query(Certificate).filter(Certificate.job_id == job.id).all()

    succeeded = sum(1 for c in certificates if c.status == CertStatus.SUCCESS)
    failed = sum(1 for c in certificates if c.status == CertStatus.FAILED)
    pending = sum(1 for c in certificates if c.status == CertStatus.PENDING)

    if pending > 0:
        logger.warning(
            "Job %s has %s pending certificates after processing",
            job.id,
            pending,
        )
        return

    if succeeded == job.total_count:
        job.status = JobStatus.COMPLETED
    elif succeeded > 0 and failed > 0:
        job.status = JobStatus.COMPLETED_WITH_ERRORS
    elif succeeded == 0 and failed == job.total_count:
        job.status = JobStatus.FAILED
    else:
        job.status = JobStatus.FAILED

    job.finished_at = datetime.now(timezone.utc)
    db.commit()
