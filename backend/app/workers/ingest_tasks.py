"""Celery tasks for document ingestion.

The main task ``process_document`` downloads the original file from MinIO,
parses it with the correct pipeline, creates ``Chunk`` records, annotates
them with keywords, and enqueues ``embed_chunks`` to generate vectors.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.pipelines.factory import PipelineFactory
from app.services.keyword_service import KeywordService
from app.services.sensitive_info_service import SensitiveInfoService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async_engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    future=True,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


def _build_s3_client():
    protocol = "https" if settings.MINIO_SECURE else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{protocol}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
    )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document(self, doc_id: str) -> Dict[str, Any]:
    """Celery task that ingests a single document end-to-end."""
    logger.info("Starting ingest for document %s", doc_id)
    try:
        result = asyncio.run(_process_document_async(doc_id))
        return result
    except Exception as exc:
        logger.exception("Ingest failed for document %s", doc_id)
        asyncio.run(_mark_failed(doc_id, str(exc), {"retry_count": self.request.retries}))
        raise self.retry(exc=exc) from exc


async def _process_document_async(doc_id: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, UUID(doc_id))
        if document is None:
            raise ValueError(f"Document {doc_id} not found")

        # Update status to processing.
        document.status = "processing"
        document.processing_info = {
            **(document.processing_info or {}),
            "stage": "downloading",
            "message": "Downloading source file",
        }
        await session.commit()

        # Resolve file path.
        file_path = await _download_document(document)

        # Determine pipeline.
        file_type = _resolve_file_type(document)
        pipeline = PipelineFactory.get_pipeline(file_type)

        document.processing_info = {
            **(document.processing_info or {}),
            "stage": "parsing",
            "pipeline": pipeline.__class__.__name__,
        }
        await session.commit()

        # Parse chunks.
        raw_chunks = pipeline.process(
            file_path,
            doc_id,
            metadata=dict(document.metadata_ or {}),
        )

        document.processing_info = {
            **(document.processing_info or {}),
            "stage": "annotating",
            "chunks_parsed": len(raw_chunks),
        }
        await session.commit()

        if not raw_chunks:
            document.status = "indexed"
            document.processing_info = {
                **(document.processing_info or {}),
                "stage": "completed",
                "message": "No chunks produced",
            }
            await session.commit()
            return {"doc_id": doc_id, "chunks": 0}

        # Keyword annotation and sensitive information scanning.
        keyword_svc = KeywordService(session)
        sensitive_svc = SensitiveInfoService(session)
        chunk_records: List[Chunk] = []
        for idx, raw in enumerate(raw_chunks):
            chunk = Chunk(
                doc_id=UUID(doc_id),
                content=raw["content"],
                modality=raw.get("modality", "text"),
                chunk_index=raw.get("chunk_index", idx),
                position_info=raw.get("position_info") or {},
                metadata_={},
                status="pending",
            )
            await keyword_svc.annotate_chunk(chunk)
            chunk_meta = {
                **(raw.get("metadata") or {}),
                **(chunk.metadata_ or {}),
            }
            chunk.metadata_ = chunk_meta
            chunk_records.append(chunk)

        # Run PII / keyword / NER detection and persist findings in metadata.
        await sensitive_svc.scan_chunks(chunk_records)
        high_severity_count = sum(
            1
            for c in chunk_records
            if (c.metadata_ or {}).get("max_builtin_severity") in {"L3", "L4"}
        )

        session.add_all(chunk_records)
        await session.commit()

        chunk_ids = [str(c.id) for c in chunk_records]

        # Update document status before embedding.
        document.status = "processing"
        document.processing_info = {
            **(document.processing_info or {}),
            "stage": "embedding_queued",
            "chunks_created": len(chunk_records),
            "chunk_ids": chunk_ids,
            "sensitive_scan": {
                "chunks_scanned": len(chunk_records),
                "chunks_with_findings": sum(
                    1 for c in chunk_records if (c.metadata_ or {}).get("has_sensitive_findings")
                ),
                "high_severity_chunks": high_severity_count,
            },
        }
        await session.commit()

    # Enqueue embedding task after the transaction is committed.
    from app.workers.embed_tasks import embed_chunks

    embed_chunks.delay(chunk_ids)
    logger.info("Enqueued embedding for %s chunks of document %s", len(chunk_ids), doc_id)
    return {"doc_id": doc_id, "chunks": len(chunk_ids)}


async def _download_document(document: Document) -> Path:
    """Download the document source to a temporary file."""
    if document.file_type == "LINK":
        # For link documents the storage_key is the URL itself.
        return Path(document.storage_key)

    if not document.storage_key:
        raise ValueError(f"Document {document.id} has no storage_key")

    s3 = _build_s3_client()
    suffix = Path(document.filename).suffix or ".bin"
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()

    def _download():
        try:
            s3.download_file(
                settings.MINIO_BUCKET,
                document.storage_key,
                str(temp_path),
            )
        except ClientError as exc:
            raise RuntimeError(f"Failed to download {document.storage_key}: {exc}") from exc

    await asyncio.to_thread(_download)
    return temp_path


def _resolve_file_type(document: Document) -> str:
    if document.file_type == "LINK":
        return "link"
    return (document.file_type or Path(document.filename).suffix).lower().lstrip(".")


async def _mark_failed(
    doc_id: str, error: str, extra: Dict[str, Any] | None = None
) -> None:
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, UUID(doc_id))
        if document is None:
            return
        document.status = "failed"
        document.processing_info = {
            **(document.processing_info or {}),
            "stage": "failed",
            "error": error,
            **(extra or {}),
        }
        await session.commit()
