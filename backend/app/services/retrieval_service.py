import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheManager
from app.models.chunk import Chunk
from app.pipelines.keyword_annotator import LEVEL_ORDER
from app.retrieval.bm25_client import bm25_client
from app.retrieval.embedding_client import embedding_client
from app.retrieval.rerank_client import rerank_client
from app.retrieval.vector_store import get_vector_store
from app.services.keyword_service import KeywordService
from app.services.permission_service import PermissionService
from app.core.metrics import (
    rag_retrieval_duration_seconds,
    rag_rerank_total,
    rag_rerank_reordered_total,
    rag_zero_result_total,
    rag_top_doc_concentration,
    rag_rerank_fallback_total,
)


class RetrievalService:
    """检索与重排序服务：向量 + BM25 + RRF + Cross-Encoder"""

    RRF_K: int = 60

    async def search(
        self,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        kb_ids: List[UUID],
        modalities: List[str] = None,
        top_k: int = 10,
        rerank_top_k: int = 5,
        mode: str = "hybrid",
    ) -> List[Dict[str, Any]]:
        """
        完整检索流程：
        1. 权限过滤条件
        2. 向量检索 / BM25检索 / 混合检索(RRF)
        3. 加载Chunk完整信息
        4. 字段级权限过滤 + 关键词级别过滤
        5. Re-rank

        Args:
            db: 数据库会话
            user_id: 当前用户ID
            query: 查询文本
            kb_ids: 知识库ID列表
            modalities: 模态过滤，默认 ["text", "image", "table", "link"]
            top_k: 每路召回数量
            rerank_top_k: 重排序后返回数量
            mode: "hybrid" | "semantic" | "keyword"
        """
        import time

        modalities = modalities or ["text", "image", "table", "link"]
        mode = mode.lower()
        timer = time.perf_counter()
        if mode not in {"hybrid", "semantic", "keyword"}:
            mode = "hybrid"

        cache = CacheManager()
        perm_service = PermissionService(db, cache)
        keyword_service = KeywordService(db)

        # 通用权限数据
        user_level = await perm_service.get_user_security_level(user_id)
        user_level_value = LEVEL_ORDER.get(user_level, 0)
        denied_docs = await perm_service.get_user_denied_documents(user_id)
        denied_tags = await perm_service.get_user_denied_tags(user_id)
        allowed_types = await perm_service.get_user_allowed_file_types(user_id)
        if modalities and allowed_types:
            allowed_types = allowed_types & set(modalities)

        candidates: List[Dict[str, Any]] = []
        vector_hits: List[Dict[str, Any]] = []
        bm25_hits: List[Dict[str, Any]] = []

        # 1. 向量检索
        if mode in ("hybrid", "semantic"):
            vector_filter = await perm_service.build_vector_filter(
                user_id=user_id,
                kb_ids=[str(k) for k in kb_ids],
                modalities=list(allowed_types) if allowed_types else modalities,
            )
            query_embedding = await embedding_client.embed(query)
            vector_store = get_vector_store()

            if "image" in modalities:
                image_results = await asyncio.to_thread(
                    vector_store.search_image,
                    query_embedding,
                    vector_filter,
                    top_k=top_k,
                )
                vector_hits.extend(image_results)

            text_results = await asyncio.to_thread(
                vector_store.search_text,
                query_embedding,
                vector_filter,
                top_k=max(top_k * 5, 50),
            )
            vector_hits.extend(text_results)

        # 2. BM25 检索
        if mode in ("hybrid", "keyword"):
            bm25_hits = await bm25_client.search(
                db=db,
                query=query,
                kb_ids=kb_ids,
                top_k=top_k * 2,
                denied_doc_ids=list(denied_docs),
                denied_tags=list(denied_tags),
                modalities=list(allowed_types) if allowed_types else modalities,
            )

        # 3. 结果融合
        if mode == "hybrid":
            candidates = self._rrf_fusion(vector_hits, bm25_hits)
        elif mode == "semantic":
            candidates = vector_hits
        else:
            candidates = bm25_hits

        # 3.5 文档级去重（D40 垄断问题修复）
        if candidates:
            candidates = self._diversify_by_document(candidates, per_doc_limit=2)

        # 3.6 文档级 MMR（提升 Hit@1 多样性）
        if candidates:
            candidates = self._mmr_rerank(
                candidates,
                lambda_param=0.6,
                top_k=top_k * 2,
            )

        if not candidates:
            return []

        # 4. 加载Chunk完整信息
        chunk_ids = list(
            {
                hit.get("chunk_id") or hit.get("id")
                for hit in candidates
                if hit.get("chunk_id") or hit.get("id")
            }
        )

        result = await db.execute(
            select(Chunk).where(Chunk.id.in_([UUID(cid) for cid in chunk_ids]))
        )
        chunks = {str(c.id): c for c in result.scalars().all()}

        # 5. 权限 + 关键词过滤 + 字段级权限
        filtered = []
        seen_chunks: set = set()
        for hit in candidates:
            chunk_id = hit.get("chunk_id") or hit.get("id")
            if not chunk_id or chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)

            chunk = chunks.get(chunk_id)
            if not chunk:
                continue

            # 文档黑名单兜底
            if str(chunk.doc_id) in denied_docs:
                continue

            # 字段级权限
            if not await perm_service.check_field_permission(user_id, chunk):
                continue

            meta = chunk.metadata_ or {}
            chunk_level_value = meta.get("max_keyword_level_value") or LEVEL_ORDER.get(
                meta.get("max_keyword_level", "L0"), 0
            )

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
                "rerank_score": None,
                "filtered": False,
            }

            # 关键词降级
            if chunk_level_value > user_level_value:
                item["content"] = "[内容涉及更高敏感级别，已过滤]"
                item["filtered"] = True

            filtered.append(item)

        # 6. Re-rank
        reranked = await rerank_client.rerank(query, filtered, top_k=rerank_top_k)
        rag_retrieval_duration_seconds.labels(mode=mode).observe(
            time.perf_counter() - timer
        )

        # 7. BadCase 监控指标埋点
        import logging
        logger = logging.getLogger(__name__)

        # 7.1 Rerank 排序变化统计
        if reranked and filtered:
            before_ids = [x["chunk_id"] for x in filtered[:rerank_top_k]]
            after_ids = [x["chunk_id"] for x in reranked[:rerank_top_k]]
            reordered = sum(1 for a, b in zip(before_ids, after_ids) if a != b)
            rag_rerank_total.labels(mode=mode).inc()
            if reordered > 0:
                rag_rerank_reordered_total.labels(mode=mode).inc(reordered)

        # 7.2 0 结果告警
        if not reranked:
            rag_zero_result_total.labels(mode=mode).inc()

        # 7.3 文档集中度（Top-1 文档占比）
        if reranked and len(reranked) >= 2:
            top_doc_id = reranked[0].get("doc_id")
            if top_doc_id:
                same_doc_count = sum(1 for r in reranked if r.get("doc_id") == top_doc_id)
                concentration = same_doc_count / len(reranked)
                rag_top_doc_concentration.labels(mode=mode).observe(concentration)
                if concentration >= 0.8:
                    logger.warning(
                        "BadCase 预警: top_doc_concentration=%.2f mode=%s query=%r",
                        concentration, mode, query,
                    )

        # 7.4 Rerank fallback 告警
        fallback_count = sum(1 for r in reranked if r.get("rerank_status") == "fallback_no_change")
        if fallback_count > 0:
            rag_rerank_fallback_total.labels(mode=mode).inc(fallback_count)

        return reranked

    async def semantic_search(
        self,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        kb_ids: List[UUID],
        modalities: List[str] = None,
        top_k: int = 10,
        rerank_top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """纯向量检索入口。"""
        return await self.search(
            db=db,
            user_id=user_id,
            query=query,
            kb_ids=kb_ids,
            modalities=modalities,
            top_k=top_k,
            rerank_top_k=rerank_top_k,
            mode="semantic",
        )

    async def keyword_search(
        self,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        kb_ids: List[UUID],
        modalities: List[str] = None,
        top_k: int = 10,
        rerank_top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """纯BM25检索入口。"""
        return await self.search(
            db=db,
            user_id=user_id,
            query=query,
            kb_ids=kb_ids,
            modalities=modalities,
            top_k=top_k,
            rerank_top_k=rerank_top_k,
            mode="keyword",
        )

    async def hybrid_search(
        self,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        kb_ids: List[UUID],
        modalities: List[str] = None,
        top_k: int = 10,
        rerank_top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """混合检索入口。"""
        return await self.search(
            db=db,
            user_id=user_id,
            query=query,
            kb_ids=kb_ids,
            modalities=modalities,
            top_k=top_k,
            rerank_top_k=rerank_top_k,
            mode="hybrid",
        )

    def _rrf_fusion(
        self,
        vector_hits: List[Dict[str, Any]],
        bm25_hits: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion across vector and BM25 result lists.

        score_rrf = sum(1 / (k + rank)) for each list the chunk appears in.
        """
        k = self.RRF_K
        rrf_scores: Dict[str, float] = {}
        hit_by_id: Dict[str, Dict[str, Any]] = {}

        def _add_hits(hits: List[Dict[str, Any]]) -> None:
            # Preserve input order as the rank; assume each list is already
            # sorted by descending relevance score.
            for rank, hit in enumerate(hits, start=1):
                chunk_id = hit.get("chunk_id") or hit.get("id")
                if not chunk_id:
                    continue
                rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (
                    k + rank
                )
                if chunk_id not in hit_by_id:
                    hit_by_id[chunk_id] = hit

        _add_hits(vector_hits)
        _add_hits(bm25_hits)

        # Sort by RRF score descending and assemble a unified candidate list.
        sorted_ids = sorted(
            rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True
        )
        fused: List[Dict[str, Any]] = []
        for chunk_id in sorted_ids:
            item = hit_by_id[chunk_id].copy()
            item["score"] = rrf_scores[chunk_id]
            item["chunk_id"] = chunk_id
            fused.append(item)

        return fused

    def _diversify_by_document(
        self, candidates: List[Dict[str, Any]], per_doc_limit: int = 2
    ) -> List[Dict[str, Any]]:
        """Limit the number of chunks per document to avoid one large document
        drowning out smaller ones in the candidate pool."""
        by_doc: Dict[str, List[Dict[str, Any]]] = {}
        for hit in candidates:
            doc_id = hit.get("doc_id") or hit.get("id", "unknown")
            by_doc.setdefault(str(doc_id), []).append(hit)
        diversified: List[Dict[str, Any]] = []
        for doc_id, hits in by_doc.items():
            diversified.extend(hits[:per_doc_limit])
        return diversified

    def _mmr_rerank(
        self,
        candidates: List[Dict[str, Any]],
        embeddings: Optional[Dict[str, List[float]]] = None,
        lambda_param: float = 0.6,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Maximal Marginal Relevance reranking for document diversity.

        Args:
            candidates: List of candidate chunks with 'score' and optionally 'embedding'.
            embeddings: Optional dict mapping chunk_id -> embedding vector.
                       If None, only doc_id-based diversity is applied.
            lambda_param: Trade-off between relevance (1.0) and diversity (0.0).
            top_k: Number of results to return.

        Returns:
            Reranked list of chunks with MMR-based diversity.
        """
        if not candidates:
            return candidates

        # Normalize scores to [0, 1]
        max_score = max(c.get("score", 0) for c in candidates)
        min_score = min(c.get("score", 0) for c in candidates)
        score_range = max(max_score - min_score, 1e-9)

        for c in candidates:
            c["_norm_score"] = (c.get("score", 0) - min_score) / score_range

        selected: List[Dict[str, Any]] = []
        remaining = list(candidates)

        while len(selected) < top_k and remaining:
            best_idx = -1
            best_mmr = -float("inf")

            for i, cand in enumerate(remaining):
                # Relevance component
                relevance = cand["_norm_score"]

                # Diversity penalty: -max similarity to already-selected docs
                diversity_penalty = 0.0
                cand_doc = cand.get("doc_id", "")
                cand_chunk_id = cand.get("chunk_id", "")

                for sel in selected:
                    # Strong penalty if same doc_id
                    if cand_doc and sel.get("doc_id") == cand_doc:
                        diversity_penalty = max(diversity_penalty, 0.9)
                    # Otherwise compute chunk embedding similarity
                    elif embeddings and cand_chunk_id in embeddings and sel.get("chunk_id") in embeddings:
                        vec_a = embeddings[cand_chunk_id]
                        vec_b = embeddings[sel.get("chunk_id")]
                        # Cosine similarity
                        dot = sum(a * b for a, b in zip(vec_a, vec_b))
                        na = sum(a * a for a in vec_a) ** 0.5
                        nb = sum(b * b for b in vec_b) ** 0.5
                        sim = dot / (na * nb) if na * nb > 0 else 0.0
                        diversity_penalty = max(diversity_penalty, sim)

                mmr = lambda_param * relevance - (1 - lambda_param) * diversity_penalty

                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i

            if best_idx >= 0:
                selected.append(remaining.pop(best_idx))

        # Clean up temporary field
        for c in selected:
            c.pop("_norm_score", None)

        return selected


retrieval_service = RetrievalService()
