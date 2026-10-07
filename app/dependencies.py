from functools import lru_cache

from app.config import get_settings
from app.database import SessionLocal
from app.services.storage import FileSystemStorage


def get_session_factory():
    return SessionLocal


@lru_cache
def get_storage() -> FileSystemStorage:
    settings = get_settings()
    return FileSystemStorage(settings.storage_dir)
