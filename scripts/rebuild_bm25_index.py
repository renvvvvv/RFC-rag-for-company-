#!/usr/bin/env python3
"""
2026-07-02: 新增脚本 - 重建 BM25 索引
用于将现有数据的 content_tsv 从 simple 配置更新为 chinese 配置
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase


async def rebuild_all_kb():
    """重建所有知识库的 BM25 索引"""
    # 2026-07-02: 在容器内运行，使用 Docker 网络的 postgres 地址
    print(f"连接数据库: {settings.async_database_url.split('@')[1]}")

    engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        future=True,
    )

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        # 获取所有知识库
        result = await session.execute(select(KnowledgeBase.id))
        kb_ids = [row[0] for row in result.all()]

        print(f"找到 {len(kb_ids)} 个知识库")

        for kb_id in kb_ids:
            print(f"\n处理知识库: {kb_id}")

            # 更新该知识库下所有活跃 chunk 的 content_tsv
            stmt = (
                Chunk.__table__.update()
                .where(Chunk.doc_id == Document.id)
                .where(Document.kb_id == kb_id)
                .where(Chunk.status == "active")
                .values(
                    content_tsv=func.to_tsvector(
                        "chinese",
                        func.coalesce(Chunk.content, "")
                    )
                )
            )

            result = await session.execute(stmt)
            updated = result.rowcount or 0
            print(f"  更新了 {updated} 个 chunk")

        await session.commit()
        print(f"\n✅ 完成！共处理 {len(kb_ids)} 个知识库")


if __name__ == "__main__":
    print("开始重建 BM25 索引（simple → chinese）...")
    asyncio.run(rebuild_all_kb())
