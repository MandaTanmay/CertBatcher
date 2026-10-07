from pathlib import Path


class FileSystemStorage:
    """
    Simple filesystem-backed storage for certificate PDFs.

    Files are stored as: <base_dir>/<job_id>/<certificate_id>.pdf
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, job_id: str, certificate_id: str, data: bytes) -> str:
        """
        Save data to storage and return the relative path.

        Args:
            job_id: Job identifier
            certificate_id: Certificate identifier
            data: Bytes to save

        Returns:
            Relative path from base_dir (e.g., "job_id/certificate_id.pdf")
        """
        job_dir = self.base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        file_path = job_dir / f"{certificate_id}.pdf"
        file_path.write_bytes(data)

        relative_path = f"{job_id}/{certificate_id}.pdf"
        return relative_path

    def read(self, relative_path: str) -> bytes:
        """
        Read data from storage by relative path.

        Args:
            relative_path: Relative path from base_dir

        Returns:
            File contents as bytes

        Raises:
            ValueError: If path attempts to escape base_dir
            FileNotFoundError: If file does not exist
        """
        resolved_path = self._resolve_path(relative_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        return resolved_path.read_bytes()

    def exists(self, relative_path: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            relative_path: Relative path from base_dir

        Returns:
            True if file exists, False otherwise
        """
        try:
            resolved_path = self._resolve_path(relative_path)
            return resolved_path.exists()
        except ValueError:
            return False

    def _resolve_path(self, relative_path: str) -> Path:
        """
        Resolve a relative path and verify it stays within base_dir.

        Args:
            relative_path: Relative path from base_dir

        Returns:
            Absolute Path

        Raises:
            ValueError: If path attempts to escape base_dir
        """
        base_path = self.base_dir.resolve()
        resolved = (base_path / relative_path).resolve()

        try:
            resolved.relative_to(base_path)
        except ValueError:
            raise ValueError(f"Path traversal attempt detected: {relative_path}")

        return resolved
