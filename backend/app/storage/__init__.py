"""Pluggable file storage factory."""
from app.config import settings

from .base import BaseFileStorage
from .local import LocalFileStorage
from .s3 import S3FileStorage

_storage_instance: BaseFileStorage | None = None


def get_file_storage() -> BaseFileStorage:
    """Return the configured file storage singleton."""
    global _storage_instance
    if _storage_instance is None:
        backend = settings.FILE_STORAGE_BACKEND.lower()
        if backend == "local":
            _storage_instance = LocalFileStorage()
        else:
            _storage_instance = S3FileStorage()
    return _storage_instance


__all__ = [
    "BaseFileStorage",
    "S3FileStorage",
    "LocalFileStorage",
    "get_file_storage",
]
