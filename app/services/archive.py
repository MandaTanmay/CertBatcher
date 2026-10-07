from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.models import Certificate
from app.services.storage import FileSystemStorage


def create_certificates_zip(
    certificates: list[Certificate],
    storage: FileSystemStorage,
) -> bytes:
    archive = BytesIO()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
        for certificate in certificates:
            if not certificate.file_path or not storage.exists(certificate.file_path):
                continue
            data = storage.read(certificate.file_path)
            zip_file.writestr(f"certificate-{certificate.id}.pdf", data)
    return archive.getvalue()
