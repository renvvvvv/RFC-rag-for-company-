"""S3/MinIO-backed file storage implementation."""
import asyncio
import logging
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings

from .base import BaseFileStorage

logger = logging.getLogger(__name__)


class S3FileStorage(BaseFileStorage):
    """File storage using a boto3 S3 client (compatible with MinIO)."""

    def __init__(self) -> None:
        protocol = "https" if settings.MINIO_SECURE else "http"
        self._client = boto3.client(
            "s3",
            endpoint_url=f"{protocol}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._bucket = settings.MINIO_BUCKET

    async def upload(self, key: str, data: bytes, content_type: str | None = None) -> None:
        kwargs: dict = {"Bucket": self._bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        await asyncio.to_thread(self._client.put_object, **kwargs)

    async def download(self, key: str) -> bytes:
        def _download() -> bytes:
            obj = self._client.get_object(Bucket=self._bucket, Key=key)
            return obj["Body"].read()

        return await asyncio.to_thread(_download)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=key
        )

    async def get_stream(self, key: str) -> tuple[BinaryIO, str]:
        def _get_object() -> dict:
            return self._client.get_object(Bucket=self._bucket, Key=key)

        obj = await asyncio.to_thread(_get_object)
        body = obj["Body"]
        content_type = obj.get("ContentType") or "application/octet-stream"
        return body, content_type

    async def exists(self, key: str) -> bool:
        def _head_object() -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=key)
                return True
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchKey"):
                    return False
                raise

        return await asyncio.to_thread(_head_object)
