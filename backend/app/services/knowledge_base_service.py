from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.core.exceptions import NotFoundException

class KnowledgeBaseService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_kb(self, kb_data: KnowledgeBaseCreate, owner_id: UUID) -> KnowledgeBase:
        kb = KnowledgeBase(
            name=kb_data.name,
            description=kb_data.description,
            owner_id=str(owner_id),
            config=kb_data.config or {},
            status="active"
        )
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb
    
    async def get_kb(self, kb_id: UUID) -> KnowledgeBase:
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise NotFoundException(f"知识库 {kb_id} 不存在")
        return kb
    
    async def list_kbs(self, skip: int = 0, limit: int = 100) -> List[KnowledgeBase]:
        result = await self.db.execute(
            select(KnowledgeBase).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def update_kb(self, kb_id: UUID, kb_data: KnowledgeBaseUpdate) -> KnowledgeBase:
        kb = await self.get_kb(kb_id)
        update_data = kb_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(kb, field, value)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb
    
    async def delete_kb(self, kb_id: UUID):
        kb = await self.get_kb(kb_id)
        await self.db.delete(kb)
        await self.db.commit()
