import uuid
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import boto3
from botocore.config import Config
from app.models.document import Document
from app.models.chunk import Chunk
from app.schemas.document import DocumentLinkCreate
from app.config import settings
from app.core.exceptions import NotFoundException

class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1"
        )
        self.bucket = settings.MINIO_BUCKET
    
    async def upload_document(
        self,
        kb_id: UUID,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        created_by: UUID,
        metadata: Optional[dict] = None
    ) -> Document:
        """上传文档到MinIO并创建记录"""
        file_type = self._detect_file_type(filename, content_type)
        storage_key = f"{kb_id}/{uuid.uuid4()}_{filename}"
        
        # 上传文件到MinIO
        self.s3.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=file_bytes,
            ContentType=content_type
        )
        
        tags = (metadata or {}).pop("tags", []) if isinstance(metadata, dict) else []
        doc = Document(
            kb_id=str(kb_id),
            filename=filename,
            file_type=file_type,
            file_size=len(file_bytes),
            mime_type=content_type,
            storage_key=storage_key,
            status="pending",
            processing_info={"tags": tags},
            metadata=metadata or {},
            created_by=str(created_by)
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc
    
    async def create_link_document(
        self,
        kb_id: UUID,
        link_data: DocumentLinkCreate,
        created_by: UUID
    ) -> Document:
        doc = Document(
            kb_id=str(kb_id),
            filename=link_data.url,
            file_type="link",
            file_size=0,
            mime_type="text/html",
            storage_key=link_data.url,
            status="pending",
            processing_info={"tags": link_data.tags or []},
            metadata=link_data.metadata or {},
            created_by=str(created_by)
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc
    
    async def get_document(self, doc_id: UUID) -> Document:
        result = await self.db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise NotFoundException(f"文档 {doc_id} 不存在")
        return doc
    
    async def list_documents(
        self,
        kb_id: UUID,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple:
        query = select(Document).where(Document.kb_id == str(kb_id))
        if status:
            query = query.where(Document.status == status)
        
        total_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar()
        
        result = await self.db.execute(query.offset(skip).limit(limit))
        items = result.scalars().all()
        return total, items
    
    async def delete_document(self, doc_id: UUID):
        doc = await self.get_document(doc_id)
        
        # 删除MinIO文件
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=doc.storage_key)
        except Exception:
            pass
        
        # 删除Chunk记录
        await self.db.execute(
            select(Chunk).where(Chunk.doc_id == str(doc_id))
        )
        # 注：Chunk删除和向量删除需要额外处理
        
        await self.db.delete(doc)
        await self.db.commit()
    
    async def update_status(
        self,
        doc_id: UUID,
        status: str,
        processing_info: Optional[dict] = None
    ):
        doc = await self.get_document(doc_id)
        doc.status = status
        if processing_info:
            doc.processing_info.update(processing_info)
        await self.db.commit()
    
    def _detect_file_type(self, filename: str, content_type: str) -> str:
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        type_map = {
            "doc": "document", "docx": "document",
            "pdf": "pdf",
            "xls": "excel", "xlsx": "excel", "csv": "excel",
            "jpg": "image", "jpeg": "image", "png": "image",
            "gif": "image", "webp": "image",
            "mp4": "video", "avi": "video", "mov": "video",
            "txt": "document",
            "link": "link"
        }
        return type_map.get(ext, "unknown")
