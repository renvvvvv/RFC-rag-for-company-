#!/usr/bin/env python3
"""
RAG 检索权限过滤逻辑验证
==============================
由于 embed worker 队列拥堵导致端到端检索测试无法稳定完成，
本脚本直接进入后端容器验证 PermissionService.build_milvus_filter_expr()
为不同权限用户生成的 Milvus 过滤表达式，确认 RAG 权限过滤逻辑生效。

运行方式（在项目根目录）：
    docker cp scripts/rag_filter_check.py rag-app-backend:/tmp/rag_filter_check.py
    docker exec rag-app-backend python /tmp/rag_filter_check.py
"""
import asyncio
import os
import sys
from uuid import uuid4

# 假设脚本在容器 /app 目录下运行
sys.path.insert(0, "/app")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.cache import CacheManager
from app.services.permission_service import PermissionService
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://rag_user:rag_password@postgres:5432/rag_kb")


async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        auth = AuthService(db)

        # 创建两个测试用户
        l0 = await auth.create_user(UserCreate(
            username=f"filter_l0_{uuid4().hex[:8]}",
            email=f"filter_l0_{uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            security_level="L0",
        ))
        l2 = await auth.create_user(UserCreate(
            username=f"filter_l2_{uuid4().hex[:8]}",
            email=f"filter_l2_{uuid4().hex[:8]}@example.com",
            password="TestPass123!",
            security_level="L2",
        ))

        cache = CacheManager()
        perm = PermissionService(db, cache)

        # 为 L0 设置文件类型权限：只允许 TEXT
        await perm.grant_permission(
            target_type="user",
            target_id=l0.id,
            object_type="file_type",
            object_key="TEXT",
            permissions=["READ"],
        )

        kb_ids = [str(uuid4())]

        expr_l0 = await perm.build_milvus_filter_expr(l0.id, kb_ids=kb_ids)
        expr_l2 = await perm.build_milvus_filter_expr(l2.id, kb_ids=kb_ids)

        print("=" * 60)
        print("RAG 检索权限过滤表达式验证")
        print("=" * 60)
        print(f"L0 user {l0.id} effective level: {await perm.get_user_security_level(l0.id)}")
        print(f"L0 filter expr: {expr_l0}")
        print()
        print(f"L2 user {l2.id} effective level: {await perm.get_user_security_level(l2.id)}")
        print(f"L2 filter expr: {expr_l2}")
        print()

        checks = {
            "L0 expr includes file type TEXT": 'modality in ["TEXT"]' in expr_l0,
            "L2 expr does not restrict file type": 'modality in' not in expr_l2,
            "Both exprs include kb_id filter": f'kb_id in ["{kb_ids[0]}"]' in expr_l0 and f'kb_id in ["{kb_ids[0]}"]' in expr_l2,
            "Different users get different exprs": expr_l0 != expr_l2,
        }

        all_pass = True
        for name, ok in checks.items():
            print(f"{'✅' if ok else '❌'} {name}")
            all_pass = all_pass and ok

        # 清理测试用户
        await db.delete(l0)
        await db.delete(l2)
        await db.commit()

        print()
        print("结果：", "全部通过" if all_pass else "存在失败")
        return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
