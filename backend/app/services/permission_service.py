from typing import List, Set, Dict, Optional, Any
from uuid import UUID
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.group import UserGroup
from app.models.permission import (
    FileTypePermission, DocumentPermission, FieldPermission,
    TagPermission, GroupPermission
)
from app.models.chunk import Chunk
from app.models.tag import Tag
from app.core.cache import CacheManager
from app.core.exceptions import PermissionDeniedException
from app.services.group_service import GroupService

LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}

class PermissionResult:
    ALLOW = "ALLOW"
    DENY = "DENY"
    PARTIAL = "PARTIAL"
    NONE = "NONE"

class PermissionService:
    def __init__(self, db: AsyncSession, cache: CacheManager):
        self.db = db
        self.cache = cache
        self.group_service = GroupService(db)
    
    def _max_level(self, levels: List[str]) -> str:
        if not levels:
            return "L0"
        max_val = max(LEVEL_ORDER.get(l, 0) for l in levels)
        for k, v in LEVEL_ORDER.items():
            if v == max_val:
                return k
        return "L0"
    
    async def get_user_groups(self, user_id: UUID) -> List[UserGroup]:
        return await self.group_service.get_user_groups(user_id)
    
    async def get_user_security_level(self, user_id: UUID) -> str:
        """获取用户有效安全级别"""
        cached = await self.cache.get_user_security_level(str(user_id))
        if cached:
            return cached
        
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return "L0"
        
        groups = await self.get_user_groups(user_id)
        levels = [user.security_level or "L0"]
        levels.extend([g.max_security_level or "L0" for g in groups])
        
        effective = self._max_level(levels)
        await self.cache.set_user_security_level(str(user_id), effective)
        return effective
    
    async def get_user_allowed_file_types(self, user_id: UUID) -> Set[str]:
        """获取用户允许的文件类型"""
        cached = await self.cache.get_user_file_types(str(user_id))
        if cached:
            return cached
        
        groups = await self.get_user_groups(user_id)
        group_ids = [str(g.id) for g in groups]
        
        result = await self.db.execute(
            select(FileTypePermission).where(
                or_(
                    FileTypePermission.target_type == "user",
                    FileTypePermission.target_id.in_(group_ids)
                )
            )
        )
        perms = result.scalars().all()
        
        # DENY优先
        denied = set()
        allowed = set()
        for p in perms:
            if "DENY" in p.permissions or "NONE" in p.permissions:
                denied.add(p.file_type)
            elif "READ" in p.permissions:
                allowed.add(p.file_type)
        
        final_allowed = allowed - denied
        await self.cache.set_user_file_types(str(user_id), final_allowed)
        return final_allowed
    
    async def check_document_permission(self, user_id: UUID, doc_id: UUID) -> str:
        """检查用户对文档的权限"""
        cached = await self.cache.get_user_doc_permission(str(user_id), str(doc_id))
        if cached:
            return cached
        
        groups = await self.get_user_groups(user_id)
        group_ids = [str(g.id) for g in groups]
        
        result = await self.db.execute(
            select(DocumentPermission).where(
                DocumentPermission.doc_id == doc_id,
                or_(
                    and_(DocumentPermission.target_type == "user", DocumentPermission.target_id == str(user_id)),
                    and_(DocumentPermission.target_type == "group", DocumentPermission.target_id.in_(group_ids))
                )
            )
        )
        perms = result.scalars().all()
        
        final_perm = PermissionResult.NONE
        for p in perms:
            if p.permission == "ADMIN":
                final_perm = "ADMIN"
                break
            elif p.permission == "WRITE":
                final_perm = "WRITE"
            elif p.permission == "READ" and final_perm == PermissionResult.NONE:
                final_perm = "READ"
            elif p.permission == "DENY":
                final_perm = PermissionResult.DENY
                break
        
        await self.cache.set_user_doc_permission(str(user_id), str(doc_id), final_perm)
        return final_perm
    
    async def get_user_denied_documents(self, user_id: UUID) -> Set[str]:
        """获取用户明确拒绝的文档ID"""
        groups = await self.get_user_groups(user_id)
        group_ids = [str(g.id) for g in groups]
        
        result = await self.db.execute(
            select(DocumentPermission.doc_id).where(
                DocumentPermission.permission == PermissionResult.DENY,
                or_(
                    and_(DocumentPermission.target_type == "user", DocumentPermission.target_id == str(user_id)),
                    and_(DocumentPermission.target_type == "group", DocumentPermission.target_id.in_(group_ids))
                )
            )
        )
        return {str(row[0]) for row in result.all()}
    
    async def get_user_allowed_tags(self, user_id: UUID) -> Set[str]:
        cached = await self.cache.get_user_tag_permission(str(user_id))
        if cached:
            return set(cached.get("allowed", []))
        
        groups = await self.get_user_groups(user_id)
        group_ids = [str(g.id) for g in groups]
        
        result = await self.db.execute(
            select(TagPermission).where(
                or_(
                    and_(TagPermission.target_type == "user", TagPermission.target_id == str(user_id)),
                    and_(TagPermission.target_type == "group", TagPermission.target_id.in_(group_ids))
                )
            )
        )
        perms = result.scalars().all()
        
        allowed = set()
        denied = set()
        for p in perms:
            allowed.update(p.allowed_tags or [])
            denied.update(p.denied_tags or [])
        
        await self.cache.set_user_tag_permission(str(user_id), {"allowed": list(allowed), "denied": list(denied)})
        return allowed
    
    async def get_user_denied_tags(self, user_id: UUID) -> Set[str]:
        cached = await self.cache.get_user_tag_permission(str(user_id))
        if cached:
            return set(cached.get("denied", []))
        await self.get_user_allowed_tags(user_id)  # 预热缓存
        cached = await self.cache.get_user_tag_permission(str(user_id))
        return set(cached.get("denied", []))
    
    async def check_field_permission(self, user_id: UUID, chunk: Chunk) -> bool:
        """检查Chunk的字段级权限"""
        if not chunk.position_info:
            return True
        
        position = chunk.position_info
        position_type = position.get("type")
        
        cached = await self.cache.get_user_field_permission(str(chunk.doc_id), str(user_id))
        if cached:
            field_configs = cached
        else:
            result = await self.db.execute(
                select(FieldPermission).where(
                    FieldPermission.doc_id == chunk.doc_id,
                    or_(
                        and_(FieldPermission.target_type == "user", FieldPermission.target_id == str(user_id))
                    )
                )
            )
            perms = result.scalars().all()
            # 简化：取第一个
            field_configs = perms[0].excel_config if perms and perms[0].excel_config else {}
            await self.cache.set_user_field_permission(str(chunk.doc_id), str(user_id), field_configs)
        
        if position_type == "excel":
            return self._check_excel_permission(position, field_configs)
        elif position_type == "word":
            return self._check_word_permission(position, field_configs)
        
        return True
    
    def _check_excel_permission(self, position: Dict, config: Dict) -> bool:
        sheet_name = position.get("sheet_name")
        sheet_config = config.get("sheet_permissions", {}).get(sheet_name, {})
        access_level = sheet_config.get("access_level", "FULL")
        
        if access_level == "FULL":
            return True
        if access_level == "NONE":
            return False
        
        chunk_columns = set(position.get("columns", []))
        denied_cols = set(sheet_config.get("denied_columns", []))
        allowed_cols = set(sheet_config.get("allowed_columns", []))
        
        if chunk_columns & denied_cols:
            return False
        if allowed_cols and not (chunk_columns <= allowed_cols):
            return False
        
        return True
    
    def _check_word_permission(self, position: Dict, config: Dict) -> bool:
        denied_headings = config.get("denied_headings", [])
        heading_path = position.get("heading_path", "")
        for h in denied_headings:
            if h in heading_path:
                return False
        return True
    
    async def build_milvus_filter_expr(
        self,
        user_id: UUID,
        kb_ids: Optional[List[str]] = None,
        modalities: Optional[List[str]] = None
    ) -> str:
        """生成Milvus权限过滤表达式"""
        conditions = ["status == 'active'"]
        
        # 知识库过滤
        if kb_ids:
            kb_list = ", ".join([f'"{str(k)}"' for k in kb_ids])
            conditions.append(f"kb_id in [{kb_list}]")
        
        # 文件类型过滤
        allowed_types = await self.get_user_allowed_file_types(user_id)
        if allowed_types:
            if modalities:
                allowed_types = allowed_types & set(modalities)
            type_list = ", ".join([f'"{t}"' for t in allowed_types])
            conditions.append(f"modality in [{type_list}]")
        
        # 文档黑名单
        denied_docs = await self.get_user_denied_documents(user_id)
        if denied_docs:
            doc_list = ", ".join([f'"{d}"' for d in denied_docs])
            conditions.append(f"doc_id not in [{doc_list}]")
        
        # 标签黑名单
        denied_tags = await self.get_user_denied_tags(user_id)
        for tag in denied_tags:
            conditions.append(f"array_not_contains(tags, '{tag}')")
        
        return " and ".join([f"({c})" for c in conditions])
