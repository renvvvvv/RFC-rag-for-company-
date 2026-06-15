from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheManager
from app.models.chunk import Chunk
from app.pipelines.keyword_annotator import LEVEL_ORDER
from app.retrieval.embedding_client import embedding_client
from app.retrieval.milvus_client import milvus_store
from app.retrieval.rerank_client import rerank_client
from app.services.keyword_service import KeywordService
from app.services.permission_service import PermissionService

class RetrievalService:
    """检索与重排序服务"""
    
    async def search(
        self,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        kb_ids: List[UUID],
        modalities: List[str] = None,
        top_k: int = 10,
        rerank_top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        完整检索流程：
        1. 权限过滤条件
        2. 向量检索
        3. 加载Chunk完整信息
        4. 字段级权限过滤 + 关键词级别过滤
        5. Re-rank
        """
        modalities = modalities or ["text", "image", "table", "link"]
        cache = CacheManager()
        perm_service = PermissionService(db, cache)
        keyword_service = KeywordService(db)
        
        # 1. 构建Milvus过滤表达式
        filter_expr = await perm_service.build_milvus_filter_expr(
            user_id=user_id,
            kb_ids=[str(k) for k in kb_ids],
            modalities=modalities
        )
        
        # 2. 生成query embedding
        query_embedding = await embedding_client.embed(query)
        
        # 3. 多模态检索
        candidates = []
        if "image" in modalities:
            image_results = milvus_store.search_image(query_embedding, filter_expr, top_k=top_k)
            candidates.extend(image_results)
        
        text_results = milvus_store.search_text(query_embedding, filter_expr, top_k=top_k * 2)
        candidates.extend(text_results)
        
        if not candidates:
            return []
        
        # 4. 加载Chunk完整信息
        doc_ids = list({hit.get("doc_id") for hit in candidates if hit.get("doc_id")})
        chunk_ids = list({hit.get("chunk_id") or hit.get("id") for hit in candidates if hit.get("chunk_id") or hit.get("id")})
        
        result = await db.execute(
            select(Chunk).where(Chunk.id.in_([UUID(cid) for cid in chunk_ids]))
        )
        chunks = {str(c.id): c for c in result.scalars().all()}
        
        # 5. 权限 + 关键词过滤
        user_level = await perm_service.get_user_security_level(user_id)
        user_level_value = LEVEL_ORDER.get(user_level, 0)
        
        filtered = []
        for hit in candidates:
            chunk_id = hit.get("chunk_id") or hit.get("id")
            chunk = chunks.get(chunk_id)
            if not chunk:
                continue
            
            # 字段级权限
            if not await perm_service.check_field_permission(user_id, chunk):
                continue
            
            meta = chunk.metadata_ or {}
            chunk_level_value = meta.get("max_keyword_level_value") or LEVEL_ORDER.get(meta.get("max_keyword_level", "L0"), 0)
            
            item = {
                "chunk_id": str(chunk.id),
                "doc_id": str(chunk.doc_id),
                "content": chunk.content,
                "modality": chunk.modality or "text",
                "position_info": chunk.position_info or {},
                "max_keyword_level": meta.get("max_keyword_level", "L0"),
                "max_keyword_level_value": chunk_level_value,
                "tags": meta.get("tags", []),
                "score": hit.get("score", 0),
            }
            
            # 关键词降级：如果chunk级别高于用户，标记过滤
            if chunk_level_value > user_level_value:
                item["content"] = "[内容涉及更高敏感级别，已过滤]"
                item["filtered"] = True
            
            filtered.append(item)
        
        # 去重
        seen = set()
        deduped = []
        for item in filtered:
            cid = item["chunk_id"]
            if cid not in seen:
                seen.add(cid)
                deduped.append(item)
        
        # 6. Re-rank
        reranked = await rerank_client.rerank(query, deduped, top_k=rerank_top_k)
        return reranked

retrieval_service = RetrievalService()
