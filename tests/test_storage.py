import pytest

from app.services.storage import FileSystemStorage


def test_save_creates_expected_directory_and_file(tmp_path):
    storage = FileSystemStorage(tmp_path)
    data = b"test pdf data"

    relative_path = storage.save("job-123", "cert-456", data)

    assert relative_path == "job-123/cert-456.pdf"
    assert (tmp_path / "job-123" / "cert-456.pdf").exists()
    assert (tmp_path / "job-123" / "cert-456.pdf").read_bytes() == data


def test_save_returns_relative_path(tmp_path):
    storage = FileSystemStorage(tmp_path)
    data = b"test pdf data"

    relative_path = storage.save("job-123", "cert-456", data)

    assert relative_path == "job-123/cert-456.pdf"
    assert str(tmp_path) not in relative_path


def test_saved_bytes_can_be_read_back(tmp_path):
    storage = FileSystemStorage(tmp_path)
    data = b"test pdf data"

    storage.save("job-123", "cert-456", data)
    read_data = storage.read("job-123/cert-456.pdf")

    assert read_data == data


def test_exists_returns_true_for_existing_file(tmp_path):
    storage = FileSystemStorage(tmp_path)
    data = b"test pdf data"

    storage.save("job-123", "cert-456", data)

    assert storage.exists("job-123/cert-456.pdf") is True


def test_exists_returns_false_for_missing_file(tmp_path):
    storage = FileSystemStorage(tmp_path)

    assert storage.exists("job-123/cert-456.pdf") is False


def test_nested_job_directories_created_automatically(tmp_path):
    storage = FileSystemStorage(tmp_path)
    data = b"test pdf data"

    storage.save("job-abc", "cert-xyz", data)

    assert (tmp_path / "job-abc").exists()
    assert (tmp_path / "job-abc").is_dir()


def test_path_traversal_is_rejected(tmp_path):
    storage = FileSystemStorage(tmp_path)

    with pytest.raises(ValueError, match="Path traversal"):
        storage.read("../etc/passwd")


def test_path_traversal_via_absolute_path_is_rejected(tmp_path):
    storage = FileSystemStorage(tmp_path)

    with pytest.raises(ValueError, match="Path traversal"):
        storage.read("/etc/passwd")


def test_path_with_shared_base_name_is_rejected(tmp_path):
    storage = FileSystemStorage(tmp_path)

    with pytest.raises(ValueError, match="Path traversal"):
        storage.read("../" + tmp_path.name + "-sibling/secret.txt")




def test_empty_pdf_bytes_can_be_stored(tmp_path):
    storage = FileSystemStorage(tmp_path)
    data = b""

    storage.save("job-123", "cert-456", data)
    read_data = storage.read("job-123/cert-456.pdf")

    assert read_data == data


def test_normal_pdf_bytes_can_be_stored(tmp_path):
    storage = FileSystemStorage(tmp_path)
    data = b"%PDF-1.4 test pdf content"

    storage.save("job-123", "cert-456", data)
    read_data = storage.read("job-123/cert-456.pdf")

    assert read_data == data
