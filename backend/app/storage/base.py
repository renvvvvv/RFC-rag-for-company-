"""Abstract base class for pluggable file storage backends."""
from abc import ABC, abstractmethod
from typing import BinaryIO


class BaseFileStorage(ABC):
    """Unified interface for file storage backends (S3/MinIO or local filesystem)."""

    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Upload ``data`` to the given ``key``."""
        ...

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download the object at ``key`` and return its contents as bytes."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete the object at ``key``."""
        ...

    @abstractmethod
    async def get_stream(self, key: str) -> tuple[BinaryIO, str]:
        """Return a readable binary stream and the object's content type."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return whether an object exists at ``key``."""
        ...
