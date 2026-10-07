from io import BytesIO

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_storage
from app.models import Certificate, CertStatus, Job
from app.schemas import (
    CertificateResult,
    CertificateResultsResponse,
    Counts,
    JobCreateRequest,
    JobCreatedResponse,
    JobStatusResponse,
)
from app.services.archive import create_certificates_zip
from app.services.job_service import create_job, get_certificate_counts
from app.services.processor import process_job
from app.services.storage import FileSystemStorage

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post(
    "/",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreatedResponse,
)
def create_job_endpoint(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    settings = get_settings()

    if len(request.recipients) > settings.max_recipients_per_job:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Too many recipients. Maximum is {settings.max_recipients_per_job}",
        )

    if not request.recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recipients list cannot be empty",
        )

    job = create_job(db, request)

    background_tasks.add_task(process_job, job.id)

    return JobCreatedResponse(
        id=job.id,
        status=job.status,
        total=job.total_count,
        status_url=f"/api/jobs/{job.id}/",
    )


def _get_job_or_404(db: Session, job_id: str) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.get("/{job_id}/", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    counts = get_certificate_counts(db, job.id, job.total_count)
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        total=job.total_count,
        counts=Counts(**counts),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        fields=job.field_definitions or [],
    )


@router.get(
    "/{job_id}/certificates/",
    response_model=CertificateResultsResponse,
)
def get_certificate_results(job_id: str, db: Session = Depends(get_db)):
    _get_job_or_404(db, job_id)
    certificates = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.row_index.asc())
        .all()
    )
    return CertificateResultsResponse(
        job_id=job_id,
        items=[
            CertificateResult(
                id=certificate.id,
                row_index=certificate.row_index,
                recipient_name=certificate.recipient_name,
                recipient_email=certificate.recipient_email,
                status=certificate.status,
                error_message=certificate.error_message,
                file_path=certificate.file_path,
                generated_at=certificate.generated_at,
                data=certificate.raw_data or {},
            )
            for certificate in certificates
        ],
    )


@router.get("/{job_id}/certificates/{certificate_id}/download")
def download_certificate(
    job_id: str,
    certificate_id: str,
    db: Session = Depends(get_db),
    storage: FileSystemStorage = Depends(get_storage),
):
    _get_job_or_404(db, job_id)
    certificate = (
        db.query(Certificate)
        .filter(
            Certificate.id == certificate_id,
            Certificate.job_id == job_id,
        )
        .first()
    )
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )
    if certificate.status != CertStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate is not available for download",
        )
    if not certificate.file_path or not storage.exists(certificate.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file not found",
        )

    try:
        data = storage.read(certificate.file_path)
    except (FileNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file not found",
        ) from None

    return StreamingResponse(
        BytesIO(data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="certificate-{certificate.id}.pdf"'
            )
        },
    )


@router.get("/{job_id}/download")
def download_certificates_zip(
    job_id: str,
    db: Session = Depends(get_db),
    storage: FileSystemStorage = Depends(get_storage),
):
    job = _get_job_or_404(db, job_id)
    certificates = (
        db.query(Certificate)
        .filter(
            Certificate.job_id == job.id,
            Certificate.status == CertStatus.SUCCESS,
        )
        .order_by(Certificate.row_index.asc())
        .all()
    )
    available_certificates = [
        certificate
        for certificate in certificates
        if certificate.file_path and storage.exists(certificate.file_path)
    ]
    if not available_certificates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No generated certificates available",
        )

    archive = create_certificates_zip(available_certificates, storage)
    return StreamingResponse(
        BytesIO(archive),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="certificates-{job.id}.zip"'
        },
    )
