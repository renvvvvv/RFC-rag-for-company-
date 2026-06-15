from typing import Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheManager
from app.pipelines.keyword_annotator import LEVEL_ORDER
from app.services.keyword_service import KeywordService
from app.services.permission_service import PermissionService

class SecurityGateway:
    """API安全网关：根据文档/查询敏感度决定调用策略"""
    
    async def decide_api_strategy(
        self,
        db: AsyncSession,
        user_id: UUID,
        context_chunks: list,
        query: str
    ) -> Dict[str, Any]:
        """
        三级策略：
        - L4绝密：本地处理，禁止调用外部API
        - L3机密：实体脱敏后调用API
        - L2及以下：直接调用API
        """
        cache = CacheManager()
        perm_service = PermissionService(db, cache)
        keyword_service = KeywordService(db)
        
        user_level = await perm_service.get_user_security_level(user_id)
        user_level_value = LEVEL_ORDER.get(user_level, 0)
        
        # 上下文最大敏感级别
        max_ctx_level = 0
        for chunk in context_chunks:
            max_ctx_level = max(
                max_ctx_level,
                chunk.get("max_keyword_level_value") or LEVEL_ORDER.get(chunk.get("max_keyword_level", "L0"), 0)
            )
        
        # 查询本身敏感级别
        annotator = await keyword_service._get_annotator()
        query_result = annotator.annotate(query)
        query_level_value = query_result.max_level_value
        
        max_level = max(user_level_value, max_ctx_level, query_level_value)
        
        if max_level >= 4:
            strategy = "local_only"
            reason = "绝密内容禁止调用外部API"
        elif max_level == 3:
            strategy = "masked_api"
            reason = "机密内容需实体脱敏后调用API"
        else:
            strategy = "direct_api"
            reason = "可直接调用外部API"
        
        return {
            "strategy": strategy,
            "max_level": max_level,
            "reason": reason
        }
    
    def mask_entities(self, text: str) -> str:
        """L3机密内容：对常见实体做脱敏"""
        import re
        text = re.sub(r"1[3-9]\d{9}", "[PHONE]", text)
        text = re.sub(r"\d{17}[\dXx]", "[IDCARD]", text)
        text = re.sub(r"[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}", "[EMAIL]", text)
        text = re.sub(r"\d+\.?\d*\s*[万元]", "[MONEY]", text)
        return text

security_gateway = SecurityGateway()
