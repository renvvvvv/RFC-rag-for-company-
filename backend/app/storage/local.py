"""Local filesystem-backed file storage implementation."""
import asyncio
import io
import logging
import mimetypes
from pathlib import Path
from typing import BinaryIO

import aiofiles

from app.config import settings

from .base import BaseFileStorage

logger = logging.getLogger(__name__)


class LocalFileStorage(BaseFileStorage):
    """File storage using the local filesystem under ``settings.LOCAL_STORAGE_PATH``."""

    def __init__(self) -> None:
        self._base_path = Path(settings.LOCAL_STORAGE_PATH)

    def _resolve_path(self, key: str) -> Path:
        """Resolve a storage key to an absolute filesystem path.

        The key is treated as a relative path below ``LOCAL_STORAGE_PATH``.
        """
        return self._base_path / key

    async def upload(self, key: str, data: bytes, content_type: str | None = None) -> None:
        path = self._resolve_path(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

    async def download(self, key: str) -> bytes:
        path = self._resolve_path(key)
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        path = self._resolve_path(key)
        try:
            await asyncio.to_thread(path.unlink)
        except FileNotFoundError:
            return

        # Remove empty parent directories up to (but not including) the base path.
        current = path.parent
        while current != self._base_path and current.is_relative_to(self._base_path):
            try:
                await asyncio.to_thread(current.rmdir)
                current = current.parent
            except OSError:
                break

    async def get_stream(self, key: str) -> tuple[BinaryIO, str]:
        path = self._resolve_path(key)
        content_type = (
            mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        )
        # Return a synchronous in-memory stream so callers can read it the same
        # way they read S3's StreamingBody.
        data = await self.download(key)
        return io.BytesIO(data), content_type

    async def exists(self, key: str) -> bool:
        path = self._resolve_path(key)
        return await asyncio.to_thread(path.is_file)
