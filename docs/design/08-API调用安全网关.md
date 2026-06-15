# 08. API调用安全网关

> 版本: v1.0  
> 日期: 2026-06-10  
> 状态: 方案设计阶段  
> 关联文档: [企业级私有化多模态RAG系统-全量技术方案](../企业级私有化多模态RAG系统-全量技术方案.md)

---

## 目录

1. [设计目标](#1-设计目标)
2. [安全调用完整流程](#2-安全调用完整流程)
3. [内容安全评估](#3-内容安全评估)
4. [三级处理策略](#4-三级处理策略)
5. [权限感知压缩](#5-权限感知压缩)
6. [API请求格式示例](#6-api请求格式示例)
7. [返回结果校验](#7-返回结果校验)
8. [审计日志设计](#8-审计日志设计)
9. [脱敏还原策略](#9-脱敏还原策略)

---

## 1. 设计目标

### 1.1 问题背景

本系统在多模态RAG Pipeline中依赖 **minimax-m3** 外部API提供视频分段视觉描述、图片内容理解等核心能力。然而，minimax-m3 作为第三方云服务，存在以下安全风险：

| 风险类型 | 风险描述 | 潜在后果 |
|----------|----------|----------|
| **数据泄露** | 检索召回的上下文可能包含机密信息，直接发送至外部API | 商业机密、个人隐私、核心技术外泄 |
| **权限穿透** | 不同安全级别的内容混杂在同一请求中，低权限用户可能通过API间接获取高权限信息 | 越权访问、信息泄露 |
| **返回污染** | 外部LLM可能编造、幻觉或植入有害内容 | 误导用户、合规风险 |
| **审计缺失** | 无法追溯哪些数据被发送到了外部API | 安全事件无法溯源 |
| **合规违规** | 违反数据分级保护要求（如《数据安全法》《个人信息保护法》） | 法律风险、行政处罚 |

### 1.2 核心设计目标

本方案在调用 minimax-m3 外部API时建立 **数据安全控制网关**，实现以下目标：

1. **分级保护**：根据内容安全等级（L0-L4）采取差异化处理策略，确保高密级数据不出域或高度脱敏后出域
2. **实体脱敏**：L3级内容中的敏感实体（人名、公司名、金额、身份证号等）在调用API前自动替换为占位符
3. **权限感知**：压缩上下文时保留安全等级标记，确保不同级别内容在压缩策略上得到区分对待
4. **返回校验**：拦截外部API返回结果中的敏感关键词，检测LLM编造/幻觉内容
5. **全程审计**：每次API调用的输入、输出、处理策略、耗时均记录安全审计日志

### 1.3 安全等级定义

```
┌─────────────────────────────────────────────────────────────────────┐
│                     内容安全等级体系 (L0-L4)                          │
├──────────┬──────────────────────────────────────────┬───────────────┤
│  等级     │ 定义                                      │ 处理策略       │
├──────────┼──────────────────────────────────────────┼───────────────┤
│   L4     │ 绝密 - 核心商业机密、未公开财务数据        │ 本地处理或      │
│          │ 核心技术参数、高管敏感信息                 │ 高度脱敏摘要    │
├──────────┼──────────────────────────────────────────┼───────────────┤
│   L3     │ 机密 - 内部运营数据、客户信息              │ 实体脱敏后      │
│          │ 员工个人信息、合同条款细节                 │ 调用外部API     │
├──────────┼──────────────────────────────────────────┼───────────────┤
│   L2     │ 内部 - 一般内部文档、会议记录              │ 直接调用API +   │
│          │ 产品文档、培训资料                         │ 权限感知压缩    │
├──────────┼──────────────────────────────────────────┼───────────────┤
│   L1     │ 公开 - 已公开的官网内容、宣传材料          │ 直接调用API     │
│          │ 公开发布的报告                             │               │
├──────────┼──────────────────────────────────────────┼───────────────┤
│   L0     │ 无标记 - 未分类内容                        │ 按L2处理       │
│          │ 或系统默认级别                             │               │
└──────────┴──────────────────────────────────────────┴───────────────┘
```

---

## 2. 安全调用完整流程

### 2.1 11步安全调用流程图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    API安全网关 - 11步调用流程                                   │
└──────────────────────────────────────────────────────────────────────────────┘

  Step 1          Step 2           Step 3           Step 4           Step 5
┌────────┐     ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
│ 检索召回│ --> │ 权限过滤│  --> │ 安全评估│  --> │策略选择│  --> │内容压缩│
│        │     │        │      │        │      │        │      │        │
│多路召回│     │四级权限│      │_assess_│      │L4/L3/  │      │保留    │
│Top-K   │     │过滤Chunk│     │content_│      │L2&L1   │      │SECURITY│
│        │     │        │      │security│      │        │      │_LEVEL  │
└────────┘     └────────┘      └────────┘      └────────┘      └────────┘
                                                                   │
                                                                   v
  Step 6          Step 7           Step 8           Step 9           Step 10
┌────────┐     ┌────────┐      ┌────────┐      ┌────────┐      ┌────────┐
│实体脱敏│ --> │ 构建请求│  --> │API调用 │  --> │返回校验│  --> │脱敏还原│
│        │     │        │      │        │      │        │      │        │
│_entity_│     │组装XML  │      │minimax-│      │Response│      │占位符→ │
│masking │     │格式上下文│     │m3      │      │Keyword │      │原文    │
│        │     │        │      │        │      │Interceptor│     │        │
└────────┘     └────────┘      └────────┘      └────────┘      └────────┘
                                                                   │
                                                                   v
                                                              ┌────────┐
                                                              │Step 11 │
                                                              │审计日志│
                                                              │        │
                                                              │记录完整│
                                                              │调用链路│
                                                              └────────┘
```

### 2.2 流程详解

| 步骤 | 环节 | 执行组件 | 关键动作 | 输出 |
|------|------|----------|----------|------|
| **1** | 检索召回 | Search Service | 多路召回Top-K候选Chunk | 候选Chunk列表 |
| **2** | 权限过滤 | Permission Service | 四级权限（类型/文档/字段/标签）过滤 | 授权Chunk列表 |
| **3** | 安全评估 | ContentSecurityAssessor | 扫描每个Chunk的敏感内容，计算max_level | 安全等级标注列表 |
| **4** | 策略选择 | SecurityPolicyRouter | 根据max_level选择L4/L3/L2处理策略 | 处理策略配置 |
| **5** | 内容压缩 | ContextCompressor | 按安全等级分组压缩，保留`[SECURITY_LEVEL]`标记 | 压缩后上下文 |
| **6** | 实体脱敏 | EntityMasker | 对L3内容执行NER+占位符替换 | 脱敏后上下文+映射表 |
| **7** | 构建请求 | RequestBuilder | 组装XML格式请求体，注入系统提示词 | 完整API请求 |
| **8** | API调用 | minimax-m3 Client | 发送HTTP请求，带熔断/重试/超时 | 原始API响应 |
| **9** | 返回校验 | ResponseValidator | 关键词拦截+编造检测+安全扫描 | 校验后响应 |
| **10** | 脱敏还原 | EntityUnmasker | 将占位符还原为原始实体 | 最终响应内容 |
| **11** | 审计日志 | AuditLogger | 记录完整调用链路，异步持久化 | 审计日志记录 |

### 2.3 流程入口代码

```python
# services/security/api_security_gateway.py

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
import hashlib
import json


class SecurityLevel(Enum):
    """内容安全等级枚举"""
    PUBLIC = 1        # L1 公开
    INTERNAL = 2      # L2 内部
    CONFIDENTIAL = 3  # L3 机密
    TOP_SECRET = 4    # L4 绝密
    UNMARKED = 0      # L0 未标记（默认按L2处理）


class ProcessingStrategy(Enum):
    """处理策略枚举"""
    LOCAL_ONLY = "local_only"           # L4: 仅本地处理
    ENTITY_MASKING = "entity_masking"   # L3: 实体脱敏后调用API
    DIRECT_WITH_COMPRESSION = "direct_with_compression"  # L2/L1: 直接调用+压缩


@dataclass
class SecurityChunk:
    """带安全等级的Chunk"""
    chunk_id: str
    doc_id: str
    content: str
    security_level: SecurityLevel
    source_metadata: Dict
    entities: List[Dict] = None  # 识别的实体列表


@dataclass
class APISecurityGatewayResult:
    """API安全网关处理结果"""
    request_id: str
    strategy: ProcessingStrategy
    api_called: bool              # 是否实际调用了外部API
    raw_response: Optional[str]   # 原始API响应
    final_response: str           # 脱敏还原后的最终响应
    audit_log_id: str             # 审计日志ID
    processing_time_ms: int
    security_risks: List[str]     # 发现的安全风险列表


class APISecurityGateway:
    """
    API调用安全网关
    
    职责：在调用minimax-m3外部API之前，对检索召回的内容进行
    安全评估、分级处理和脱敏保护。
    """
    
    def __init__(
        self,
        content_assessor,
        entity_masker,
        context_compressor,
        request_builder,
        api_client,
        response_validator,
        entity_unmasker,
        audit_logger,
        config: Dict
    ):
        self.content_assessor = content_assessor
        self.entity_masker = entity_masker
        self.context_compressor = context_compressor
        self.request_builder = request_builder
        self.api_client = api_client
        self.response_validator = response_validator
        self.entity_unmasker = entity_unmasker
        self.audit_logger = audit_logger
        self.config = config
    
    async def process(
        self,
        query: str,
        chunks: List[Dict],
        user_context: Dict,
        task_type: str = "video_description"
    ) -> APISecurityGatewayResult:
        """
        11步安全调用流程主入口
        
        Args:
            query: 用户原始查询
            chunks: 检索召回的Chunk列表（已过滤权限）
            user_context: 用户上下文（角色、部门、权限等）
            task_type: 任务类型（video_description / image_understanding / ...）
        
        Returns:
            APISecurityGatewayResult: 处理结果
        """
        request_id = self._generate_request_id()
        start_time = time.time() * 1000
        audit_payload = {
            "request_id": request_id,
            "query": query,
            "user_id": user_context.get("user_id"),
            "task_type": task_type,
            "steps": []
        }
        
        try:
            # Step 1: 检索召回（已在调用方完成，chunks为输入）
            audit_payload["steps"].append({
                "step": 1, "name": "retrieval",
                "input_chunk_count": len(chunks),
                "status": "completed"
            })
            
            # Step 2: 权限过滤（已在调用方完成，chunks为已过滤列表）
            audit_payload["steps"].append({
                "step": 2, "name": "permission_filter",
                "status": "completed",
                "note": "Filtered by Permission Service upstream"
            })
            
            # Step 3: 内容安全评估
            security_chunks = await self._step3_security_assessment(chunks)
            max_level = self._compute_max_level(security_chunks)
            audit_payload["steps"].append({
                "step": 3, "name": "security_assessment",
                "max_level": max_level.name,
                "chunk_levels": [c.security_level.name for c in security_chunks],
                "status": "completed"
            })
            
            # Step 4: 策略选择
            strategy = self._step4_select_strategy(max_level)
            audit_payload["steps"].append({
                "step": 4, "name": "strategy_selection",
                "strategy": strategy.value,
                "status": "completed"
            })
            
            # L4绝密：直接本地处理，不调用外部API
            if strategy == ProcessingStrategy.LOCAL_ONLY:
                return await self._handle_l4_local_processing(
                    request_id, query, security_chunks, 
                    user_context, audit_payload, start_time
                )
            
            # Step 5: 权限感知压缩
            compressed_context = self._step5_compress_context(
                security_chunks, strategy
            )
            audit_payload["steps"].append({
                "step": 5, "name": "context_compression",
                "compressed_length": len(compressed_context),
                "status": "completed"
            })
            
            # Step 6: 实体脱敏（仅L3策略）
            masked_context, entity_mapping = await self._step6_entity_masking(
                compressed_context, strategy
            )
            audit_payload["steps"].append({
                "step": 6, "name": "entity_masking",
                "masked_entities_count": len(entity_mapping),
                "status": "completed"
            })
            
            # Step 7: 构建请求
            request_payload = self._step7_build_request(
                query, masked_context, task_type, user_context
            )
            audit_payload["steps"].append({
                "step": 7, "name": "request_build",
                "request_size": len(json.dumps(request_payload)),
                "status": "completed"
            })
            
            # Step 8: API调用
            raw_response = await self._step8_api_call(request_payload)
            audit_payload["steps"].append({
                "step": 8, "name": "api_call",
                "api_provider": "minimax-m3",
                "status": "completed"
            })
            
            # Step 9: 返回校验
            validated_response, risks = await self._step9_validate_response(
                raw_response, entity_mapping
            )
            audit_payload["steps"].append({
                "step": 9, "name": "response_validation",
                "risks_found": risks,
                "status": "completed" if not risks else "warning"
            })
            
            # Step 10: 脱敏还原
            final_response = self._step10_unmask_entities(
                validated_response, entity_mapping
            )
            audit_payload["steps"].append({
                "step": 10, "name": "entity_unmasking",
                "status": "completed"
            })
            
            # Step 11: 审计日志
            processing_time = int(time.time() * 1000 - start_time)
            audit_log_id = await self._step11_audit_log(
                request_id, audit_payload, final_response, processing_time
            )
            
            return APISecurityGatewayResult(
                request_id=request_id,
                strategy=strategy,
                api_called=True,
                raw_response=raw_response,
                final_response=final_response,
                audit_log_id=audit_log_id,
                processing_time_ms=processing_time,
                security_risks=risks
            )
            
        except Exception as e:
            # 异常处理：记录失败审计日志
            processing_time = int(time.time() * 1000 - start_time)
            audit_payload["error"] = str(e)
            audit_payload["status"] = "failed"
            audit_log_id = await self._step11_audit_log(
                request_id, audit_payload, "", processing_time
            )
            raise APISecurityException(
                f"API Security Gateway failed: {e}",
                request_id=request_id,
                audit_log_id=audit_log_id
            )
    
    def _generate_request_id(self) -> str:
        """生成请求ID"""
        import uuid
        return f"asg_{uuid.uuid4().hex[:16]}_{int(time.time())}"
    
    def _compute_max_level(self, security_chunks: List[SecurityChunk]) -> SecurityLevel:
        """计算所有Chunk中的最高安全等级"""
        if not security_chunks:
            return SecurityLevel.UNMARKED
        return max(security_chunks, key=lambda c: c.security_level.value).security_level
    
    def _step4_select_strategy(self, max_level: SecurityLevel) -> ProcessingStrategy:
        """根据最高安全等级选择处理策略"""
        strategy_map = {
            SecurityLevel.TOP_SECRET: ProcessingStrategy.LOCAL_ONLY,
            SecurityLevel.CONFIDENTIAL: ProcessingStrategy.ENTITY_MASKING,
            SecurityLevel.INTERNAL: ProcessingStrategy.DIRECT_WITH_COMPRESSION,
            SecurityLevel.PUBLIC: ProcessingStrategy.DIRECT_WITH_COMPRESSION,
            SecurityLevel.UNMARKED: ProcessingStrategy.DIRECT_WITH_COMPRESSION,
        }
        return strategy_map.get(max_level, ProcessingStrategy.DIRECT_WITH_COMPRESSION)
```

---

## 3. 内容安全评估

### 3.1 评估架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ContentSecurityAssessor                               │
│                    内容安全评估器                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   输入: Chunk文本 + 元数据                                               │
│      │                                                                  │
│      v                                                                  │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐   │
│   │ 规则匹配引擎      │    │ NER实体识别       │    │ 标签继承检测  │   │
│   │ Rule Matcher     │    │ Entity Recognizer│    │ Tag Inheritance│  │
│   └──────────────────┘    └──────────────────┘    └──────────────┘   │
│      │                          │                        │              │
│      v                          v                        v              │
│   ┌──────────────────────────────────────────────────────────────┐    │
│   │                  综合评分 & 等级判定                          │    │
│   │              _assess_content_security()                      │    │
│   └──────────────────────────────────────────────────────────────┘    │
│      │                                                                  │
│      v                                                                  │
│   输出: SecurityLevel (L0-L4) + 风险详情 + 实体列表                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心评估函数

```python
# services/security/content_security_assessor.py

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class RiskCategory(Enum):
    """风险类别"""
    FINANCIAL = "financial"           # 财务数据
    PERSONAL_INFO = "personal_info"   # 个人信息
    BUSINESS_SECRET = "business_secret"  # 商业机密
    TECHNICAL_SECRET = "technical_secret"  # 技术机密
    LEGAL_CONTRACT = "legal_contract"  # 法律合同
    INTERNAL_STRATEGY = "internal_strategy"  # 内部战略


@dataclass
class SecurityAssessmentResult:
    """安全评估结果"""
    level: 'SecurityLevel'
    score: float                    # 0.0 - 1.0，综合风险分数
    risk_categories: List[RiskCategory]
    matched_keywords: List[Dict]    # 匹配的关键词及位置
    detected_entities: List[Dict]   # 检测到的敏感实体
    reasoning: str                  # 判定理由


class ContentSecurityAssessor:
    """
    内容安全评估器
    
    对单个Chunk进行多维度安全评估，确定其安全等级。
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.sensitive_keywords = self._load_sensitive_keywords()
        self.entity_patterns = self._load_entity_patterns()
        self.level_thresholds = {
            SecurityLevel.TOP_SECRET: 0.85,      # 风险分数 >= 0.85 -> L4
            SecurityLevel.CONFIDENTIAL: 0.60,     # 风险分数 >= 0.60 -> L3
            SecurityLevel.INTERNAL: 0.30,         # 风险分数 >= 0.30 -> L2
            SecurityLevel.PUBLIC: 0.0,            # 风险分数 < 0.30 -> L1
        }
    
    def _load_sensitive_keywords(self) -> Dict[str, List[Dict]]:
        """
        加载敏感关键词清单
        
        按风险类别组织，每个关键词包含权重和正则模式
        """
        return {
            RiskCategory.FINANCIAL: [
                {"pattern": r"营收[额]*\s*[:：]\s*[\d,]+\s*[万亿]*元", "weight": 0.9, "desc": "营收金额"},
                {"pattern": r"利润[率]*\s*[:：]\s*[\d,.]+\s*%?", "weight": 0.85, "desc": "利润率"},
                {"pattern": r"净利润\s*[:：]\s*[\d,]+\s*[万亿]*元", "weight": 0.9, "desc": "净利润"},
                {"pattern": r"估值\s*[:：]\s*[\d,]+\s*[万亿]*", "weight": 0.85, "desc": "公司估值"},
                {"pattern": r"融资金额\s*[:：]\s*[\d,]+\s*[万亿]*", "weight": 0.9, "desc": "融资金额"},
                {"pattern": r"Q[1-4].*?财报", "weight": 0.7, "desc": "季度财报"},
                {"pattern": r"未公开财务", "weight": 1.0, "desc": "未公开财务数据"},
                {"pattern": r"内部预算\s*[:：]", "weight": 0.8, "desc": "内部预算"},
                {"pattern": r"成本\s*[:：]\s*[\d,]+\s*[万亿]*", "weight": 0.7, "desc": "成本数据"},
            ],
            RiskCategory.PERSONAL_INFO: [
                {"pattern": r"身份证号\s*[:：]\s*\d{17}[\dXx]", "weight": 1.0, "desc": "身份证号"},
                {"pattern": r"\d{17}[\dXx]", "weight": 0.95, "desc": "身份证号格式"},
                {"pattern": r"银行卡号\s*[:：]\s*\d{16,19}", "weight": 0.95, "desc": "银行卡号"},
                {"pattern": r"手机号\s*[:：]\s*1[3-9]\d{9}", "weight": 0.8, "desc": "手机号"},
                {"pattern": r"1[3-9]\d{9}", "weight": 0.75, "desc": "手机号格式"},
                {"pattern": r"家庭住址\s*[:：]", "weight": 0.8, "desc": "家庭住址"},
                {"pattern": r" salary\s*[:：]\s*[\d,]+", "weight": 0.85, "desc": "薪资数据"},
                {"pattern": r"工资\s*[:：]\s*[\d,]+\s*元", "weight": 0.85, "desc": "工资金额"},
                {"pattern": r"绩效考核\s*[:：]", "weight": 0.7, "desc": "绩效考核"},
                {"pattern": r"员工编号\s*[:：]\s*[A-Z]*\d+", "weight": 0.6, "desc": "员工编号"},
            ],
            RiskCategory.BUSINESS_SECRET: [
                {"pattern": r"商业机密", "weight": 1.0, "desc": "商业机密标记"},
                {"pattern": r"保密协议\s*[（(]NDA[)）]", "weight": 0.95, "desc": "保密协议"},
                {"pattern": r"竞业禁止", "weight": 0.9, "desc": "竞业禁止条款"},
                {"pattern": r"客户名单", "weight": 0.85, "desc": "客户名单"},
                {"pattern": r"供应商信息", "weight": 0.75, "desc": "供应商信息"},
                {"pattern": r"定价策略", "weight": 0.85, "desc": "定价策略"},
                {"pattern": r"市场份额\s*[:：]\s*[\d.]+%", "weight": 0.8, "desc": "市场份额"},
                {"pattern": r"战略合作\s*[:：]", "weight": 0.7, "desc": "战略合作"},
                {"pattern": r"并购计划", "weight": 0.9, "desc": "并购计划"},
                {"pattern": r"IPO\s*计划", "weight": 0.85, "desc": "IPO计划"},
                {"pattern": r"未公开合作", "weight": 0.9, "desc": "未公开合作"},
            ],
            RiskCategory.TECHNICAL_SECRET: [
                {"pattern": r"核心算法", "weight": 0.85, "desc": "核心算法"},
                {"pattern": r"源代码", "weight": 0.9, "desc": "源代码"},
                {"pattern": r"架构设计.*?(?:(?:不)?对外公开|内部)", "weight": 0.85, "desc": "内部架构"},
                {"pattern": r"技术栈.*?(?:(?:不)?对外公开|内部)", "weight": 0.8, "desc": "内部技术栈"},
                {"pattern": r"专利.*?(?:申请中|未公开)", "weight": 0.9, "desc": "未公开专利"},
                {"pattern": r"密钥\s*[:：]\s*[\w+/=]+", "weight": 1.0, "desc": "密钥"},
                {"pattern": r"API\s*Secret", "weight": 0.95, "desc": "API Secret"},
                {"pattern": r"数据库密码", "weight": 1.0, "desc": "数据库密码"},
                {"pattern": r"内网IP\s*[:：]\s*10\.\d+\.\d+\.\d+", "weight": 0.75, "desc": "内网IP"},
                {"pattern": r"192\.168\.\d+\.\d+", "weight": 0.7, "desc": "私有IP"},
            ],
            RiskCategory.LEGAL_CONTRACT: [
                {"pattern": r"合同编号\s*[:：]", "weight": 0.7, "desc": "合同编号"},
                {"pattern": r"违约责任", "weight": 0.65, "desc": "违约责任"},
                {"pattern": r"赔偿金额\s*[:：]\s*[\d,]+", "weight": 0.85, "desc": "赔偿金额"},
                {"pattern": r"保密期限", "weight": 0.8, "desc": "保密期限"},
                {"pattern": r"知识产权归属", "weight": 0.75, "desc": "知识产权归属"},
                {"pattern": r"独家授权", "weight": 0.7, "desc": "独家授权"},
            ],
            RiskCategory.INTERNAL_STRATEGY: [
                {"pattern": r"战略规划\s*(?:202\d-[\d]*)?", "weight": 0.8, "desc": "战略规划"},
                {"pattern": r"组织架构调整", "weight": 0.85, "desc": "组织架构调整"},
                {"pattern": r"裁员计划", "weight": 0.9, "desc": "裁员计划"},
                {"pattern": r"高管变动", "weight": 0.85, "desc": "高管变动"},
                {"pattern": r"内部会议纪要", "weight": 0.75, "desc": "内部会议纪要"},
                {"pattern": r"董事会决议", "weight": 0.9, "desc": "董事会决议"},
                {"pattern": r"未公开产品", "weight": 0.85, "desc": "未公开产品"},
                {"pattern": r"产品路线图", "weight": 0.8, "desc": "产品路线图"},
            ],
        }
    
    def _load_entity_patterns(self) -> Dict[str, re.Pattern]:
        """加载实体识别正则模式"""
        return {
            "person_name": re.compile(r"[\u4e00-\u9fa5]{2,4}(?:先生|女士|总|经理|总监|CEO|CTO|CFO)?"),
            "company_name": re.compile(r"[\u4e00-\u9fa5]+(?:科技|网络|信息|软件|集团|公司|有限)"),
            "id_card": re.compile(r"\d{17}[\dXx]"),
            "phone": re.compile(r"1[3-9]\d{9}"),
            "bank_card": re.compile(r"\d{16,19}"),
            "email": re.compile(r"[\w.-]+@[\w.-]+\.\w+"),
            "amount": re.compile(r"[\d,]+(?:\.\d+)?\s*[万亿]?元"),
        }
    
    async def _assess_content_security(
        self,
        chunk: Dict,
        tag_security_levels: Optional[Dict] = None
    ) -> SecurityAssessmentResult:
        """
        评估单个Chunk的安全等级
        
        Args:
            chunk: 文档Chunk，包含 content, metadata, tags 等字段
            tag_security_levels: 标签到安全等级的映射
        
        Returns:
            SecurityAssessmentResult: 安全评估结果
        """
        text = chunk.get("content", "")
        metadata = chunk.get("metadata", {})
        tags = chunk.get("tags", [])
        
        # 1. 标签继承检测（最高优先级）
        tag_level = self._check_tag_security_level(tags, tag_security_levels)
        if tag_level and tag_level.value >= SecurityLevel.CONFIDENTIAL.value:
            return SecurityAssessmentResult(
                level=tag_level,
                score=tag_level.value / 4.0,
                risk_categories=[],
                matched_keywords=[],
                detected_entities=[],
                reasoning=f"标签继承: Chunk被打上了'{tag_level.name}'级别标签"
            )
        
        # 2. 规则匹配（关键词扫描）
        keyword_matches = self._match_sensitive_keywords(text)
        
        # 3. 实体识别
        detected_entities = self._detect_entities(text)
        entity_risk_boost = self._calculate_entity_risk_boost(detected_entities)
        
        # 4. 元数据风险加分
        metadata_risk = self._assess_metadata_risk(metadata)
        
        # 5. 计算综合风险分数
        base_score = self._calculate_base_score(keyword_matches)
        final_score = min(1.0, base_score + entity_risk_boost + metadata_risk)
        
        # 6. 等级判定
        level = self._score_to_level(final_score)
        
        # 7. 收集风险类别
        risk_categories = list(set(
            m["category"] for m in keyword_matches
        ))
        
        reasoning = self._generate_reasoning(
            level, keyword_matches, detected_entities, tag_level
        )
        
        return SecurityAssessmentResult(
            level=level,
            score=final_score,
            risk_categories=risk_categories,
            matched_keywords=keyword_matches,
            detected_entities=detected_entities,
            reasoning=reasoning
        )
    
    def _check_tag_security_level(
        self, 
        tags: List[str],
        tag_security_levels: Optional[Dict]
    ) -> Optional['SecurityLevel']:
        """检查Chunk标签继承的安全等级"""
        if not tag_security_levels:
            return None
        
        max_level = None
        for tag in tags:
            level_str = tag_security_levels.get(tag)
            if level_str:
                level = SecurityLevel[level_str.upper()]
                if not max_level or level.value > max_level.value:
                    max_level = level
        return max_level
    
    def _match_sensitive_keywords(self, text: str) -> List[Dict]:
        """匹配敏感关键词"""
        matches = []
        for category, keywords in self.sensitive_keywords.items():
            for kw in keywords:
                for m in re.finditer(kw["pattern"], text):
                    matches.append({
                        "category": category,
                        "pattern": kw["desc"],
                        "weight": kw["weight"],
                        "matched_text": m.group(),
                        "position": (m.start(), m.end())
                    })
        return matches
    
    def _detect_entities(self, text: str) -> List[Dict]:
        """检测敏感实体"""
        entities = []
        for entity_type, pattern in self.entity_patterns.items():
            for m in pattern.finditer(text):
                # 去重：过滤掉过于短或过于常见的匹配
                matched = m.group()
                if len(matched) < 2:
                    continue
                entities.append({
                    "type": entity_type,
                    "text": matched,
                    "start": m.start(),
                    "end": m.end()
                })
        return entities
    
    def _calculate_entity_risk_boost(self, entities: List[Dict]) -> float:
        """根据检测到的实体计算风险加分"""
        boost = 0.0
        high_risk_types = {"id_card", "bank_card", "email", "phone"}
        for e in entities:
            if e["type"] in high_risk_types:
                boost += 0.15
            else:
                boost += 0.05
        return min(0.5, boost)
    
    def _assess_metadata_risk(self, metadata: Dict) -> float:
        """评估元数据风险加分"""
        risk = 0.0
        # 如果元数据中有明确的安全标记
        security_tag = metadata.get("security_level", "")
        if security_tag in ["top_secret", "绝密"]:
            risk += 1.0
        elif security_tag in ["confidential", "机密"]:
            risk += 0.6
        elif security_tag in ["internal", "内部"]:
            risk += 0.3
        return risk
    
    def _calculate_base_score(self, keyword_matches: List[Dict]) -> float:
        """基于关键词匹配计算基础风险分数"""
        if not keyword_matches:
            return 0.0
        # 取最高权重 + 其他权重*0.3的累加
        sorted_weights = sorted([m["weight"] for m in keyword_matches], reverse=True)
        score = sorted_weights[0]
        for w in sorted_weights[1:]:
            score += w * 0.3
        return min(1.0, score)
    
    def _score_to_level(self, score: float) -> 'SecurityLevel':
        """将风险分数映射为安全等级"""
        if score >= self.level_thresholds[SecurityLevel.TOP_SECRET]:
            return SecurityLevel.TOP_SECRET
        elif score >= self.level_thresholds[SecurityLevel.CONFIDENTIAL]:
            return SecurityLevel.CONFIDENTIAL
        elif score >= self.level_thresholds[SecurityLevel.INTERNAL]:
            return SecurityLevel.INTERNAL
        else:
            return SecurityLevel.PUBLIC
    
    def _generate_reasoning(
        self,
        level: 'SecurityLevel',
        keyword_matches: List[Dict],
        entities: List[Dict],
        tag_level: Optional['SecurityLevel']
    ) -> str:
        """生成判定理由"""
        reasons = []
        if tag_level:
            reasons.append(f"标签继承等级: {tag_level.name}")
        if keyword_matches:
            top_kws = sorted(keyword_matches, key=lambda x: x["weight"], reverse=True)[:3]
            reasons.append(f"关键词匹配: {', '.join(k['pattern'] for k in top_kws)}")
        if entities:
            entity_types = set(e["type"] for e in entities)
            reasons.append(f"检测实体: {', '.join(entity_types)}")
        return f"等级{level.name}: " + "; ".join(reasons) if reasons else "无明显风险特征"
```

### 3.3 敏感关键词清单汇总

| 风险类别 | 关键词数量 | 最高权重 | 典型触发词 |
|----------|-----------|----------|-----------|
| **FINANCIAL（财务数据）** | 9 | 1.0 | 未公开财务、营收金额、融资金额、净利润 |
| **PERSONAL_INFO（个人信息）** | 10 | 1.0 | 身份证号、银行卡号、薪资数据、家庭住址 |
| **BUSINESS_SECRET（商业机密）** | 11 | 1.0 | 商业机密、保密协议、并购计划、未公开合作 |
| **TECHNICAL_SECRET（技术机密）** | 10 | 1.0 | 源代码、密钥、API Secret、未公开专利 |
| **LEGAL_CONTRACT（法律合同）** | 6 | 0.85 | 赔偿金额、保密期限、知识产权归属 |
| **INTERNAL_STRATEGY（内部战略）** | 8 | 0.9 | 裁员计划、董事会决议、未公开产品、组织架构调整 |

---

## 4. 三级处理策略

### 4.1 策略路由决策

```
                    max_level 判定
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        v                v                v
   ┌─────────┐     ┌─────────┐     ┌─────────────┐
   │   L4    │     │   L3    │     │  L2/L1/L0   │
   │ 绝密    │     │ 机密    │     │ 内部/公开   │
   └────┬────┘     └────┬────┘     └──────┬──────┘
        │               │                  │
        v               v                  v
   ┌─────────┐     ┌─────────┐     ┌─────────────┐
   │本地处理 │     │实体脱敏 │     │直接调用API  │
   │或摘要   │     │后调用   │     │+权限感知压缩│
   └─────────┘     └─────────┘     └─────────────┘
```

### 4.2 L4 绝密：本地处理或高度脱敏摘要

```python
# services/security/api_security_gateway.py (续)

    async def _handle_l4_local_processing(
        self,
        request_id: str,
        query: str,
        security_chunks: List[SecurityChunk],
        user_context: Dict,
        audit_payload: Dict,
        start_time: float
    ) -> APISecurityGatewayResult:
        """
        处理L4绝密内容
        
        策略：
        1. 不调用外部API
        2. 如果配置了本地LLM，使用本地模型处理
        3. 否则返回高度脱敏的摘要提示
        """
        # 检查是否有本地模型可用
        local_model_available = self.config.get("local_llm_enabled", False)
        
        if local_model_available:
            # 使用本地模型处理（数据不出域）
            local_response = await self._call_local_model(query, security_chunks)
            final_response = local_response
            api_called = False
        else:
            # 无本地模型：生成脱敏摘要提示
            final_response = self._generate_l4_masked_summary(security_chunks)
            api_called = False
        
        processing_time = int(time.time() * 1000 - start_time)
        
        # 记录L4特殊审计日志
        audit_payload["steps"].extend([
            {"step": 5, "name": "l4_local_processing", "status": "completed"},
            {"step": 6, "name": "l4_skip_api_call", "reason": "TOP_SECRET content blocked"},
            {"step": 9, "name": "l4_skip_validation", "reason": "No external API call"},
            {"step": 10, "name": "l4_skip_unmasking", "reason": "No masking applied"},
        ])
        audit_log_id = await self._step11_audit_log(
            request_id, audit_payload, final_response, processing_time
        )
        
        return APISecurityGatewayResult(
            request_id=request_id,
            strategy=ProcessingStrategy.LOCAL_ONLY,
            api_called=api_called,
            raw_response=None,
            final_response=final_response,
            audit_log_id=audit_log_id,
            processing_time_ms=processing_time,
            security_risks=["TOP_SECRET_CONTENT_DETECTED"]
        )
    
    def _generate_l4_masked_summary(self, security_chunks: List[SecurityChunk]) -> str:
        """为L4内容生成脱敏摘要（不暴露具体内容）"""
        doc_count = len(set(c.doc_id for c in security_chunks))
        level_count = sum(1 for c in security_chunks if c.security_level == SecurityLevel.TOP_SECRET)
        
        return (
            f"[系统提示] 检索到 {level_count} 条绝密级内容（来自 {doc_count} 个文档），"
            f"根据数据安全策略，未通过外部API处理。"
            f"\n\n这些内容包含高度敏感的商业或技术机密，"
            f"建议：1) 使用本地部署模型处理；2) 联系信息安全部门获取授权。"
        )
    
    async def _call_local_model(self, query: str, security_chunks: List[SecurityChunk]) -> str:
        """调用本地部署LLM（数据不出域）"""
        # 由LocalLLMService实现
        context = "\n\n".join(c.content for c in security_chunks[:5])
        return await self.config["local_llm_service"].generate(query, context)
```

### 4.3 L3 机密：实体脱敏后调用API

```python
# services/security/entity_masker.py

import re
import hashlib
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class EntityMaskMapping:
    """实体脱敏映射记录"""
    placeholder: str        # 占位符，如 <PERSON_001>
    original: str           # 原始值
    entity_type: str        # 实体类型
    position: Optional[Tuple[int, int]] = None


class EntityMasker:
    """
    实体脱敏器
    
    对L3级别内容中的敏感实体进行识别和占位符替换，
    生成可安全发送至外部API的文本。
    """
    
    # 实体类型到占位符前缀的映射
    PLACEHOLDER_PREFIX = {
        "person_name": "PERSON",
        "company_name": "COMPANY",
        "id_card": "ID_CARD",
        "phone": "PHONE",
        "bank_card": "BANK_CARD",
        "email": "EMAIL",
        "amount": "AMOUNT",
        "address": "ADDRESS",
        "date_sensitive": "DATE",
        "ip_address": "IP",
    }
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.consistent_mapping: Dict[str, str] = {}  # 全局一致映射缓存
        self.mapping_ttl = self.config.get("mapping_ttl_seconds", 3600)
    
    async def mask(
        self,
        text: str,
        strategy: str = "placeholder",  # placeholder / hash / redact
        preserve_structure: bool = True
    ) -> Tuple[str, List[EntityMaskMapping]]:
        """
        对文本进行实体脱敏
        
        Args:
            text: 原始文本
            strategy: 脱敏策略
                - placeholder: 替换为可读占位符（推荐）
                - hash: 替换为哈希值
                - redact: 替换为[REDACTED]
            preserve_structure: 是否保留文本结构（如JSON/XML格式）
        
        Returns:
            (脱敏后文本, 映射表)
        """
        # 1. 实体识别
        entities = self._extract_entities(text)
        
        # 2. 去重和排序（从后往前替换，避免位置偏移）
        unique_entities = self._deduplicate_entities(entities)
        sorted_entities = sorted(unique_entities, key=lambda e: e["start"], reverse=True)
        
        # 3. 生成占位符并替换
        mappings = []
        result = text
        
        for idx, entity in enumerate(sorted_entities):
            placeholder = self._generate_placeholder(entity, idx)
            
            # 全局一致性：相同原始值使用相同占位符
            cache_key = f"{entity['type']}:{entity['text']}"
            if cache_key in self.consistent_mapping:
                placeholder = self.consistent_mapping[cache_key]
            else:
                self.consistent_mapping[cache_key] = placeholder
            
            mapping = EntityMaskMapping(
                placeholder=placeholder,
                original=entity["text"],
                entity_type=entity["type"],
                position=(entity["start"], entity["end"])
            )
            mappings.append(mapping)
            
            # 执行替换
            result = result[:entity["start"]] + placeholder + result[entity["end"]:]
        
        return result, mappings
    
    def _extract_entities(self, text: str) -> List[Dict]:
        """提取需要脱敏的实体"""
        entities = []
        
        # 使用正则模式识别各类实体
        patterns = {
            "person_name": re.compile(
                r"[\u4e00-\u9fa5]{2,4}(?:先生|女士|总|经理|总监|主管|CEO|CTO|CFO|VP)"
            ),
            "company_name": re.compile(
                r"[\u4e00-\u9fa5A-Za-z]+(?:科技|网络|信息|软件|集团|公司|有限公司|股份|Inc\.|Ltd\.?)"
            ),
            "id_card": re.compile(r"\d{17}[\dXx]"),
            "phone": re.compile(r"1[3-9]\d{9}"),
            "bank_card": re.compile(r"\d{16,19}"),
            "email": re.compile(r"[\w.-]+@[\w.-]+\.\w+"),
            "amount": re.compile(r"[\d,]+(?:\.\d{1,2})?\s*[万亿]?\s*(?:元|美元|USD|CNY)"),
            "ip_address": re.compile(r"(?:\d{1,3}\.){3}\d{1,3}|(?:[0-9a-fA-F:]{2,})+"),
        }
        
        for entity_type, pattern in patterns.items():
            for match in pattern.finditer(text):
                entities.append({
                    "type": entity_type,
                    "text": match.group(),
                    "start": match.start(),
                    "end": match.end()
                })
        
        return entities
    
    def _deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """去重：保留最长的匹配（解决重叠问题）"""
        # 按起始位置排序，然后贪婪选择
        sorted_by_start = sorted(entities, key=lambda e: (e["start"], -e["end"]))
        result = []
        last_end = -1
        
        for e in sorted_by_start:
            if e["start"] >= last_end:
                result.append(e)
                last_end = e["end"]
        
        return result
    
    def _generate_placeholder(self, entity: Dict, index: int) -> str:
        """生成占位符"""
        prefix = self.PLACEHOLDER_PREFIX.get(entity["type"], "ENTITY")
        # 使用哈希后缀保证唯一性，同时保持可读性
        short_hash = hashlib.md5(entity["text"].encode()).hexdigest()[:4].upper()
        return f"<{prefix}_{short_hash}>"


# 在 Gateway 中的集成
def _step6_entity_masking(
    self,
    context: str,
    strategy: ProcessingStrategy
) -> Tuple[str, List[EntityMaskMapping]]:
    """Step 6: 实体脱敏"""
    if strategy != ProcessingStrategy.ENTITY_MASKING:
        # L2/L1策略：不脱敏，返回空映射
        return context, []
    
    # L3策略：执行实体脱敏
    masked_text, mappings = asyncio.get_event_loop().run_until_complete(
        self.entity_masker.mask(context, strategy="placeholder")
    )
    return masked_text, mappings
```

**实体脱敏示例：**

| 原始文本 | 脱敏后文本 | 映射记录 |
|----------|-----------|----------|
| 张三的月薪是25000元 | `<PERSON_A3F2>`的月薪是`<AMOUNT_7B1C>` | PERSON_A3F2→张三, AMOUNT_7B1C→25000元 |
| 请联系李四，手机13800138000 | 请联系`<PERSON_9E4D>`，手机`<PHONE_>2A8F>` | PERSON_9E4D→李四, PHONE_2A8F→13800138000 |
| 北京智云科技有限公司计划融资5000万美元 | `<COMPANY_C1D8>`计划融资`<AMOUNT_3F7A>` | COMPANY_C1D8→北京智云科技有限公司, AMOUNT_3F7A→5000万美元 |
| 身份证号110101199001011234 | 身份证号`<ID_CARD_5E9B>` | ID_CARD_5E9B→110101199001011234 |

### 4.4 L2/L1：直接调用API + 权限感知压缩

```python
def _step5_compress_context(
    self,
    security_chunks: List[SecurityChunk],
    strategy: ProcessingStrategy
) -> str:
    """
    Step 5: 权限感知压缩
    
    按安全等级分组压缩，保留[SECURITY_LEVEL]标记
    """
    if strategy == ProcessingStrategy.LOCAL_ONLY:
        # L4: 不压缩，直接返回本地处理提示
        return "[LOCAL_PROCESSING_ONLY]"
    
    # 按安全等级分组
    grouped = self._group_chunks_by_level(security_chunks)
    
    compressed_parts = []
    for level in [SecurityLevel.PUBLIC, SecurityLevel.INTERNAL, 
                  SecurityLevel.CONFIDENTIAL, SecurityLevel.TOP_SECRET]:
        chunks = grouped.get(level, [])
        if not chunks:
            continue
        
        # 为每组添加安全等级标记
        level_marker = f"[SECURITY_LEVEL:{level.name}]"
        
        if level == SecurityLevel.CONFIDENTIAL and strategy == ProcessingStrategy.ENTITY_MASKING:
            # L3组：保留完整内容（脱敏在Step 6处理）
            group_text = "\n\n".join(c.content for c in chunks)
            compressed_parts.append(f"{level_marker}\n{group_text}")
        else:
            # L2/L1组：按Token预算压缩
            group_text = self._compress_chunk_group(chunks, level)
            compressed_parts.append(f"{level_marker}\n{group_text}")
    
    return "\n\n---\n\n".join(compressed_parts)

def _group_chunks_by_level(
    self, 
    chunks: List[SecurityChunk]
) -> Dict[SecurityLevel, List[SecurityChunk]]:
    """按安全等级分组Chunk"""
    grouped = {}
    for chunk in chunks:
        level = chunk.security_level
        if level not in grouped:
            grouped[level] = []
        grouped[level].append(chunk)
    return grouped

def _compress_chunk_group(
    self,
    chunks: List[SecurityChunk],
    level: SecurityLevel
) -> str:
    """
    压缩单组Chunk
    
    不同级别有不同的Token预算：
    - L1 公开: 完整保留
    - L2 内部: 允许适度压缩（保留80%）
    - L3 机密: 由脱敏器处理，此处不额外压缩
    """
    if level == SecurityLevel.PUBLIC:
        # L1: 完整保留
        return "\n\n".join(c.content for c in chunks)
    
    if level == SecurityLevel.INTERNAL:
        # L2: 适度压缩 - 优先保留开头和结尾，中间可摘要
        full_text = "\n\n".join(c.content for c in chunks)
        max_tokens = self.config.get("l2_max_tokens", 2048)
        return self._truncate_or_summarize(full_text, max_tokens)
    
    # L3/L4: 不在这里压缩
    return "\n\n".join(c.content for c in chunks)

def _truncate_or_summarize(self, text: str, max_tokens: int) -> str:
    """截断或摘要文本至指定Token数"""
    # 简化实现：按字符估算（中文约1字=1token，英文约4字符=1token）
    estimated_tokens = len(text)  # 保守估计
    
    if estimated_tokens <= max_tokens:
        return text
    
    # 超出预算：保留开头30%和结尾30%，中间用[...摘要...]替代
    prefix_len = int(max_tokens * 0.3)
    suffix_len = int(max_tokens * 0.3)
    
    prefix = text[:prefix_len]
    suffix = text[-suffix_len:]
    
    return f"{prefix}\n\n[... 内容已压缩，保留 {prefix_len}+{suffix_len}/{estimated_tokens} 字符 ...]\n\n{suffix}"
```

---

## 5. 权限感知压缩

### 5.1 压缩策略矩阵

| 安全等级 | 压缩策略 | Token预算 | [SECURITY_LEVEL]标记 | 说明 |
|----------|----------|-----------|---------------------|------|
| **L4 绝密** | 不压缩，阻断出域 | 0 | `[SECURITY_LEVEL:TOP_SECRET]` | 内容不出域 |
| **L3 机密** | 完整保留（不脱敏不压缩） | 按实体数量动态调整 | `[SECURITY_LEVEL:CONFIDENTIAL]` | 保留完整文本供脱敏器处理 |
| **L2 内部** | 适度压缩 | 2048 tokens | `[SECURITY_LEVEL:INTERNAL]` | 保留80%内容，可截断中间部分 |
| **L1 公开** | 完整保留 | 无限制 | `[SECURITY_LEVEL:PUBLIC]` | 无需特殊处理 |
| **L0 未标记** | 按L2处理 | 2048 tokens | `[SECURITY_LEVEL:INTERNAL]` | 默认保守策略 |

### 5.2 压缩时保留标记的完整示例

```python
# 压缩后的上下文示例（含SECURITY_LEVEL标记）

COMPRESSED_CONTEXT_EXAMPLE = """
用户查询: "分析Q3产品发布会的关键信息"

[SECURITY_LEVEL:PUBLIC]
---
产品发布会于2026年9月15日在北京国际会议中心举行。
发布会主题为"智领未来"，共有500余名嘉宾参加。

---

[SECURITY_LEVEL:INTERNAL]
---
发布会预算为200万元，实际支出约180万元。
现场展示了3款新产品，其中产品A获得了最高关注度。
市场部反馈：发布会后官网流量增长了35%。

[... 内容已压缩，保留 614+614/2048 字符 ...]

会后调查显示，客户满意度为87%。

---

[SECURITY_LEVEL:CONFIDENTIAL]
---
<PERSON_A3F2>在发布会上透露，公司明年计划进军海外市场，预计初期投入<PERSON_7B1C>。
与<COMPANY_C1D8>的合作协议已签署，合同金额为<AMOUNT_3F7A>。
<PERSON_9E4D>的绩效考核目标中包含该项目的KPI。

---

[SECURITY_LEVEL:TOP_SECRET]
---
[内容已阻断：该部分包含绝密级信息，未通过外部API处理。]
"""
```

### 5.3 权限感知压缩器完整实现

```python
# services/security/context_compressor.py

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class CompressionResult:
    """压缩结果"""
    compressed_text: str
    original_token_count: int
    compressed_token_count: int
    compression_ratio: float
    level_breakdown: Dict[str, Dict]  # 各级别的压缩统计


class PermissionAwareCompressor:
    """
    权限感知压缩器
    
    在压缩上下文时保留SECURITY_LEVEL标记，
    确保不同安全级别的内容按各自策略处理。
    """
    
    # 各级别的Token预算
    LEVEL_BUDGETS = {
        "PUBLIC": None,        # 无限制
        "INTERNAL": 2048,      # 2K tokens
        "CONFIDENTIAL": 4096,  # 4K tokens（给脱敏器留空间）
        "TOP_SECRET": 0,       # 绝密不出域
    }
    
    def __init__(self, tokenizer=None):
        self.tokenizer = tokenizer  # 可选：真实的Tokenizer
    
    def compress(
        self,
        security_chunks: List[SecurityChunk],
        query: str
    ) -> CompressionResult:
        """
        执行权限感知压缩
        
        Args:
            security_chunks: 带安全等级的Chunk列表
            query: 用户查询（用于相关性压缩）
        
        Returns:
            CompressionResult: 压缩结果及统计
        """
        # 按级别分组
        grouped = self._group_by_level(security_chunks)
        
        level_breakdown = {}
        compressed_parts = []
        total_original = 0
        total_compressed = 0
        
        for level_name, budget in self.LEVEL_BUDGETS.items():
            level_enum = SecurityLevel[level_name]
            chunks = grouped.get(level_enum, [])
            
            if not chunks:
                continue
            
            # 计算原始Token数
            original_text = "\n\n".join(c.content for c in chunks)
            original_tokens = self._estimate_tokens(original_text)
            total_original += original_tokens
            
            if budget == 0:
                # L4: 绝密阻断
                compressed = f"[SECURITY_LEVEL:{level_name}]\n[内容已阻断：绝密级信息不出域]"
                compressed_tokens = self._estimate_tokens(compressed)
            elif budget is None:
                # L1: 完整保留
                compressed = f"[SECURITY_LEVEL:{level_name}]\n{original_text}"
                compressed_tokens = original_tokens
            else:
                # L2/L3: 按预算压缩
                compressed_text = self._compress_to_budget(original_text, budget, query)
                compressed = f"[SECURITY_LEVEL:{level_name}]\n{compressed_text}"
                compressed_tokens = self._estimate_tokens(compressed)
            
            total_compressed += compressed_tokens
            compressed_parts.append(compressed)
            
            level_breakdown[level_name] = {
                "chunk_count": len(chunks),
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "budget": budget,
            }
        
        final_text = "\n\n---\n\n".join(compressed_parts)
        
        ratio = (
            total_compressed / total_original 
            if total_original > 0 else 0
        )
        
        return CompressionResult(
            compressed_text=final_text,
            original_token_count=total_original,
            compressed_token_count=total_compressed,
            compression_ratio=ratio,
            level_breakdown=level_breakdown
        )
    
    def _group_by_level(self, chunks: List[SecurityChunk]) -> Dict[SecurityLevel, List[SecurityChunk]]:
        """按安全等级分组"""
        grouped = {}
        for c in chunks:
            grouped.setdefault(c.security_level, []).append(c)
        return grouped
    
    def _estimate_tokens(self, text: str) -> int:
        """估算Token数（简化版）"""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # 中文按字，英文按词粗略估算
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        other = len(text) - chinese_chars - sum(len(w) for w in re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words + other // 4
    
    def _compress_to_budget(
        self, 
        text: str, 
        budget: int,
        query: str
    ) -> str:
        """将文本压缩到指定Token预算"""
        current_tokens = self._estimate_tokens(text)
        
        if current_tokens <= budget:
            return text
        
        # 策略1: 如果超的不多，直接截断
        if current_tokens <= budget * 1.5:
            return self._truncate_middle(text, budget)
        
        # 策略2: 超得较多，按相关性排序后截断
        return self._relevance_based_truncate(text, query, budget)
    
    def _truncate_middle(self, text: str, budget: int) -> str:
        """从中间截断，保留开头和结尾"""
        # 简单实现：按比例截断字符
        ratio = budget / self._estimate_tokens(text)
        target_chars = int(len(text) * ratio)
        
        prefix_len = target_chars // 3
        suffix_len = target_chars // 3
        
        prefix = text[:prefix_len]
        suffix = text[-suffix_len:]
        
        return (
            f"{prefix}\n"
            f"[... 内容已压缩（中间部分省略）...]\n"
            f"{suffix}"
        )
    
    def _relevance_based_truncate(self, text: str, query: str, budget: int) -> str:
        """基于查询相关性保留最相关段落"""
        paragraphs = text.split("\n\n")
        
        # 简化相关性评分：包含查询关键词的段落得分更高
        query_terms = set(query.lower().split())
        scored = []
        for p in paragraphs:
            score = sum(1 for term in query_terms if term in p.lower())
            scored.append((score, p))
        
        # 按相关性降序排列
        scored.sort(key=lambda x: x[0], reverse=True)
        
        #  greedily 选择段落直到预算用完
        selected = []
        current_tokens = 0
        for score, p in scored:
            p_tokens = self._estimate_tokens(p)
            if current_tokens + p_tokens <= budget:
                selected.append(p)
                current_tokens += p_tokens
        
        # 恢复原始顺序
        selected_set = set(selected)
        ordered = [p for p in paragraphs if p in selected_set]
        
        if len(ordered) < len(paragraphs):
            ordered.append(f"[... 另有 {len(paragraphs) - len(ordered)} 段内容因相关性较低已省略 ...]")
        
        return "\n\n".join(ordered)
```

---

## 6. API请求格式示例

### 6.1 发送给minimax-m3的完整上下文格式

```python
# services/security/request_builder.py

import json
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom


class MinimaxM3RequestBuilder:
    """
    minimax-m3 API请求构建器
    
    将脱敏后的上下文组装为minimax-m3可识别的请求格式。
    支持XML和JSON两种格式（推荐XML，便于结构化安全标记）。
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_version = config.get("api_version", "v1")
        self.model = config.get("model", "minimax-m3")
    
    def build_xml_request(
        self,
        query: str,
        masked_context: str,
        task_type: str,
        user_context: Dict,
        security_metadata: Dict
    ) -> str:
        """
        构建XML格式的API请求
        
        XML结构包含安全元数据，便于minimax-m3侧识别处理约束。
        """
        root = Element("minimax_request")
        root.set("version", self.api_version)
        root.set("model", self.model)
        
        # 请求头 / 元数据
        meta = SubElement(root, "security_metadata")
        SubElement(meta, "request_id").text = security_metadata.get("request_id", "")
        SubElement(meta, "max_security_level").text = security_metadata.get("max_level", "INTERNAL")
        SubElement(meta, "data_origin").text = "enterprise_private_rag"
        SubElement(meta, "masking_applied").text = str(security_metadata.get("masking_applied", False)).lower()
        SubElement(meta, "entity_mapping_count").text = str(security_metadata.get("mapping_count", 0))
        
        # 系统提示词（注入安全约束）
        system = SubElement(root, "system_prompt")
        system.text = self._build_security_system_prompt(security_metadata)
        
        # 用户查询
        query_elem = SubElement(root, "user_query")
        query_elem.text = query
        
        # 上下文内容（已脱敏）
        context = SubElement(root, "context")
        
        # 按SECURITY_LEVEL标记拆分上下文段落
        segments = self._parse_context_segments(masked_context)
        for seg in segments:
            seg_elem = SubElement(context, "segment")
            seg_elem.set("security_level", seg["level"])
            seg_elem.set("source_doc_id", seg.get("doc_id", "unknown"))
            seg_elem.text = seg["content"]
        
        # 任务指令
        task = SubElement(root, "task_instruction")
        task.set("type", task_type)
        task.text = self._get_task_instruction(task_type)
        
        # 输出约束
        output = SubElement(root, "output_constraints")
        SubElement(output, "format").text = "structured_json"
        SubElement(output, "max_length").text = "2000"
        SubElement(output, "language").text = "zh-CN"
        SubElement(output, "citation_required").text = "true"
        
        # 美化输出
        rough_string = tostring(root, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def build_json_request(
        self,
        query: str,
        masked_context: str,
        task_type: str,
        user_context: Dict,
        security_metadata: Dict
    ) -> Dict:
        """构建JSON格式的API请求"""
        segments = self._parse_context_segments(masked_context)
        
        return {
            "model": self.model,
            "request_id": security_metadata.get("request_id", ""),
            "messages": [
                {
                    "role": "system",
                    "content": self._build_security_system_prompt(security_metadata)
                },
                {
                    "role": "user",
                    "content": self._build_user_content(query, segments, task_type)
                }
            ],
            "security_metadata": {
                "max_level": security_metadata.get("max_level", "INTERNAL"),
                "masking_applied": security_metadata.get("masking_applied", False),
                "entity_mapping_count": security_metadata.get("mapping_count", 0),
                "data_origin": "enterprise_private_rag"
            },
            "parameters": {
                "temperature": 0.3,
                "max_tokens": 2000,
                "top_p": 0.9
            }
        }
    
    def _build_security_system_prompt(self, security_metadata: Dict) -> str:
        """构建包含安全约束的系统提示词"""
        max_level = security_metadata.get("max_level", "INTERNAL")
        masking = security_metadata.get("masking_applied", False)
        
        prompt_parts = [
            "你是一个企业级知识库助手。请基于提供的上下文回答用户问题。",
            "",
            f"【安全约束】当前上下文最高安全等级: {max_level}",
        ]
        
        if masking:
            prompt_parts.extend([
                "【脱敏说明】上下文中包含脱敏占位符（如<PERSON_xxxx>、<AMOUNT_xxxx>），",
                "请保留这些占位符格式，不要在回答中还原或猜测原始值。",
            ])
        
        prompt_parts.extend([
            "",
            "【回答要求】",
            "1. 严格基于上下文回答，不要编造不存在的信息",
            "2. 如果上下文不足，明确说明无法回答",
            "3. 保留原文中的占位符标记",
            "4. 不要输出任何可能泄露敏感信息的内容",
            "5. 使用中文回答"
        ])
        
        return "\n".join(prompt_parts)
    
    def _build_user_content(self, query: str, segments: List[Dict], task_type: str) -> str:
        """构建用户消息内容"""
        parts = [f"任务类型: {task_type}\n", f"用户问题: {query}\n", "=== 上下文 ===\n"]
        
        for seg in segments:
            parts.append(f"[安全等级: {seg['level']}]")
            parts.append(seg["content"])
            parts.append("")
        
        parts.append("=== 请回答 ===")
        return "\n".join(parts)
    
    def _parse_context_segments(self, masked_context: str) -> List[Dict]:
        """解析含SECURITY_LEVEL标记的上下文"""
        segments = []
        current_level = "UNKNOWN"
        current_content = []
        current_doc_id = "unknown"
        
        for line in masked_context.split("\n"):
            if line.startswith("[SECURITY_LEVEL:"):
                # 保存上一个segment
                if current_content:
                    segments.append({
                        "level": current_level,
                        "doc_id": current_doc_id,
                        "content": "\n".join(current_content).strip()
                    })
                    current_content = []
                
                # 解析新级别
                level_str = line.replace("[SECURITY_LEVEL:", "").replace("]", "").strip()
                current_level = level_str
            else:
                current_content.append(line)
        
        # 保存最后一个segment
        if current_content:
            segments.append({
                "level": current_level,
                "doc_id": current_doc_id,
                "content": "\n".join(current_content).strip()
            })
        
        return segments
    
    def _get_task_instruction(self, task_type: str) -> str:
        """获取任务指令"""
        instructions = {
            "video_description": "基于视频关键帧和上下文描述，生成详细的视频内容描述。保留时间戳信息。",
            "image_understanding": "分析图片内容，提供详细的视觉描述。",
            "content_summarization": "对提供的上下文进行摘要总结，保留关键信息。",
            "qa_generation": "基于上下文回答用户问题。",
        }
        return instructions.get(task_type, "处理用户请求。")
```

### 6.2 XML请求格式示例

```xml
<?xml version="1.0" ?>
<minimax_request version="v1" model="minimax-m3">
  <security_metadata>
    <request_id>asg_a1b2c3d4e5f6_1718000000</request_id>
    <max_security_level>CONFIDENTIAL</max_security_level>
    <data_origin>enterprise_private_rag</data_origin>
    <masking_applied>true</masking_applied>
    <entity_mapping_count>5</entity_mapping_count>
  </security_metadata>
  <system_prompt>你是一个企业级知识库助手。请基于提供的上下文回答用户问题。

【安全约束】当前上下文最高安全等级: CONFIDENTIAL
【脱敏说明】上下文中包含脱敏占位符（如&lt;PERSON_xxxx&gt;、&lt;AMOUNT_xxxx&gt;），
请保留这些占位符格式，不要在回答中还原或猜测原始值。

【回答要求】
1. 严格基于上下文回答，不要编造不存在的信息
2. 如果上下文不足，明确说明无法回答
3. 保留原文中的占位符标记
4. 不要输出任何可能泄露敏感信息的内容
5. 使用中文回答</system_prompt>
  <user_query>分析Q3产品发布会的关键信息</user_query>
  <context>
    <segment security_level="PUBLIC" source_doc_id="press_release_001">
      产品发布会于2026年9月15日在北京国际会议中心举行。
      发布会主题为"智领未来"，共有500余名嘉宾参加。
    </segment>
    <segment security_level="INTERNAL" source_doc_id="marketing_report_003">
      发布会预算为200万元，实际支出约180万元。
      现场展示了3款新产品，其中产品A获得了最高关注度。
      市场部反馈：发布会后官网流量增长了35%。
    </segment>
    <segment security_level="CONFIDENTIAL" source_doc_id="contract_007">
      &lt;PERSON_A3F2&gt;在发布会上透露，公司明年计划进军海外市场，预计初期投入&lt;AMOUNT_7B1C&gt;。
      与&lt;COMPANY_C1D8&gt;的合作协议已签署，合同金额为&lt;AMOUNT_3F7A&gt;。
      &lt;PERSON_9E4D&gt;的绩效考核目标中包含该项目的KPI。
    </segment>
  </context>
  <task_instruction type="content_summarization">
    对提供的上下文进行摘要总结，保留关键信息。
  </task_instruction>
  <output_constraints>
    <format>structured_json</format>
    <max_length>2000</max_length>
    <language>zh-CN</language>
    <citation_required>true</citation_required>
  </output_constraints>
</minimax_request>
```

### 6.3 JSON请求格式示例

```json
{
  "model": "minimax-m3",
  "request_id": "asg_a1b2c3d4e5f6_1718000000",
  "messages": [
    {
      "role": "system",
      "content": "你是一个企业级知识库助手。请基于提供的上下文回答用户问题。\n\n【安全约束】当前上下文最高安全等级: CONFIDENTIAL\n【脱敏说明】上下文中包含脱敏占位符（如<PERSON_xxxx>、<AMOUNT_xxxx>），请保留这些占位符格式，不要在回答中还原或猜测原始值。\n\n【回答要求】\n1. 严格基于上下文回答，不要编造不存在的信息\n2. 如果上下文不足，明确说明无法回答\n3. 保留原文中的占位符标记\n4. 不要输出任何可能泄露敏感信息的内容\n5. 使用中文回答"
    },
    {
      "role": "user",
      "content": "任务类型: content_summarization\n用户问题: 分析Q3产品发布会的关键信息\n=== 上下文 ===\n\n[安全等级: PUBLIC]\n产品发布会于2026年9月15日在北京国际会议中心举行。发布会主题为\"智领未来\"，共有500余名嘉宾参加。\n\n[安全等级: INTERNAL]\n发布会预算为200万元，实际支出约180万元。现场展示了3款新产品，其中产品A获得了最高关注度。市场部反馈：发布会后官网流量增长了35%。\n\n[安全等级: CONFIDENTIAL]\n<PERSON_A3F2>在发布会上透露，公司明年计划进军海外市场，预计初期投入<AMOUNT_7B1C>。与<COMPANY_C1D8>的合作协议已签署，合同金额为<AMOUNT_3F7A>。<PERSON_9E4D>的绩效考核目标中包含该项目的KPI。\n\n=== 请回答 ==="
    }
  ],
  "security_metadata": {
    "max_level": "CONFIDENTIAL",
    "masking_applied": true,
    "entity_mapping_count": 5,
    "data_origin": "enterprise_private_rag"
  },
  "parameters": {
    "temperature": 0.3,
    "max_tokens": 2000,
    "top_p": 0.9
  }
}
```

---

## 7. 返回结果校验

### 7.1 校验架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ResponseValidator                                     │
│                    返回结果校验器                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   minimax-m3 原始响应                                                    │
│      │                                                                  │
│      v                                                                  │
│   ┌──────────────────┐                                                  │
│   │ ResponseKeywordInterceptor                                         │
│   │ 敏感关键词拦截器   │                                                  │
│   │ - 黑名单关键词匹配  │                                                  │
│   │ - 占位符格式校验   │                                                  │
│   └──────────────────┘                                                  │
│      │                                                                  │
│      v                                                                  │
│   ┌──────────────────┐                                                  │
│   │ HallucinationDetector                                              │
│   │ LLM编造/幻觉检测   │                                                  │
│   │ - 来源一致性检查   │                                                  │
│   │ - 事实可验证性检查  │                                                  │
│   └──────────────────┘                                                  │
│      │                                                                  │
│      v                                                                  │
│   ┌──────────────────┐                                                  │
│   │ SafetyScanner                                                        │
│   │ 安全性扫描        │                                                  │
│   │ - 有害内容检测     │                                                  │
│   │ - 隐私泄露扫描     │                                                  │
│   └──────────────────┘                                                  │
│      │                                                                  │
│      v                                                                  │
│   输出: (校验后响应, 风险列表) 或抛出 ValidationException              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 ResponseKeywordInterceptor 实现

```python
# services/security/response_validator.py

import re
import json
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum


class ValidationRiskLevel(Enum):
    """校验风险等级"""
    CRITICAL = "critical"    # 阻断响应
    HIGH = "high"            # 标记风险，需人工审核
    MEDIUM = "medium"        # 记录日志，允许通过
    LOW = "low"              # 仅记录


@dataclass
class ValidationRisk:
    """校验风险记录"""
    risk_type: str
    level: ValidationRiskLevel
    description: str
    evidence: str
    position: Optional[Tuple[int, int]] = None


class ResponseKeywordInterceptor:
    """
    返回关键词拦截器
    
    检查minimax-m3返回的内容是否包含：
    1. 不应出现的敏感实体（说明脱敏被还原）
    2. 黑名单关键词
    3. 占位符格式被破坏
    """
    
    # 绝对禁止出现的敏感模式（说明脱敏失效或LLM还原了实体）
    SENSITIVE_PATTERNS = {
        "id_card": re.compile(r"\d{17}[\dXx]"),
        "phone": re.compile(r"1[3-9]\d{9}"),
        "bank_card": re.compile(r"\d{16,19}"),
        "email": re.compile(r"[\w.-]+@[\w.-]+\.\w+"),
        "internal_ip": re.compile(r"(?:10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2[0-9]|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)"),
    }
    
    # 黑名单关键词（不应出现在返回中）
    BLACKLIST_KEYWORDS = [
        "内部机密", "严禁外传", "保密期限", "核心算法细节",
        "源代码如下", "数据库密码是", "API密钥为",
        # 可根据实际业务扩展
    ]
    
    # 占位符格式正则（用于校验格式完整性）
    PLACEHOLDER_PATTERN = re.compile(r"<([A-Z_]+)_([0-9A-F]{4})>")
    
    def __init__(self, custom_blacklist: Optional[List[str]] = None):
        self.blacklist = set(self.BLACKLIST_KEYWORDS)
        if custom_blacklist:
            self.blacklist.update(custom_blacklist)
    
    def intercept(
        self,
        response_text: str,
        entity_mapping: List['EntityMaskMapping']
    ) -> Tuple[str, List[ValidationRisk]]:
        """
        拦截并校验响应内容
        
        Args:
            response_text: minimax-m3返回的原始文本
            entity_mapping: 实体脱敏映射表
        
        Returns:
            (校验后文本, 风险列表)
            
        Raises:
            ResponseValidationException: 发现严重风险时抛出
        """
        risks = []
        
        # 1. 检查敏感实体泄露（脱敏被还原）
        entity_risks = self._check_entity_leakage(response_text, entity_mapping)
        risks.extend(entity_risks)
        
        # 2. 检查黑名单关键词
        blacklist_risks = self._check_blacklist_keywords(response_text)
        risks.extend(blacklist_risks)
        
        # 3. 检查占位符格式完整性
        placeholder_risks = self._check_placeholder_integrity(response_text, entity_mapping)
        risks.extend(placeholder_risks)
        
        # 4. 检查是否包含"猜测"或"推测"原始值
        inference_risks = self._check_entity_inference(response_text, entity_mapping)
        risks.extend(inference_risks)
        
        # 根据风险等级决定处理方式
        critical_risks = [r for r in risks if r.level == ValidationRiskLevel.CRITICAL]
        if critical_risks:
            raise ResponseValidationException(
                f"检测到 {len(critical_risks)} 项严重安全风险，响应已阻断",
                risks=critical_risks
            )
        
        return response_text, risks
    
    def _check_entity_leakage(
        self,
        text: str,
        entity_mapping: List['EntityMaskMapping']
    ) -> List[ValidationRisk]:
        """检查是否有脱敏实体被还原泄露"""
        risks = []
        original_values = {m.original for m in entity_mapping}
        
        for original in original_values:
            if original in text:
                risks.append(ValidationRisk(
                    risk_type="ENTITY_LEAKAGE",
                    level=ValidationRiskLevel.CRITICAL,
                    description=f"脱敏实体被还原泄露: {original[:10]}...",
                    evidence=f"发现原始值出现在响应中",
                    position=self._find_position(text, original)
                ))
        
        # 同时检查通用敏感模式
        for pattern_name, pattern in self.SENSITIVE_PATTERNS.items():
            for match in pattern.finditer(text):
                matched_text = match.group()
                # 排除占位符格式的匹配
                if self.PLACEHOLDER_PATTERN.match(matched_text):
                    continue
                risks.append(ValidationRisk(
                    risk_type="SENSITIVE_PATTERN_LEAKAGE",
                    level=ValidationRiskLevel.CRITICAL,
                    description=f"检测到敏感模式泄露: {pattern_name}",
                    evidence=matched_text[:20] + "...",
                    position=(match.start(), match.end())
                ))
        
        return risks
    
    def _check_blacklist_keywords(self, text: str) -> List[ValidationRisk]:
        """检查黑名单关键词"""
        risks = []
        for keyword in self.blacklist:
            if keyword in text:
                risks.append(ValidationRisk(
                    risk_type="BLACKLIST_KEYWORD",
                    level=ValidationRiskLevel.HIGH,
                    description=f"包含黑名单关键词: {keyword}",
                    evidence=text[max(0, text.find(keyword)-20):text.find(keyword)+len(keyword)+20]
                ))
        return risks
    
    def _check_placeholder_integrity(
        self,
        text: str,
        entity_mapping: List['EntityMaskMapping']
    ) -> List[ValidationRisk]:
        """检查占位符格式是否被破坏"""
        risks = []
        expected_placeholders = {m.placeholder for m in entity_mapping}
        
        # 检查所有出现的占位符格式
        for match in self.PLACEHOLDER_PATTERN.finditer(text):
            placeholder = match.group()
            if placeholder not in expected_placeholders:
                # 可能是LLM自己生成的假占位符
                risks.append(ValidationRisk(
                    risk_type="FAKE_PLACEHOLDER",
                    level=ValidationRiskLevel.HIGH,
                    description=f"发现未授权的占位符: {placeholder}",
                    evidence=placeholder,
                    position=(match.start(), match.end())
                ))
        
        return risks
    
    def _check_entity_inference(
        self,
        text: str,
        entity_mapping: List['EntityMaskMapping']
    ) -> List[ValidationRisk]:
        """检查LLM是否试图"猜测"或"推断"脱敏实体的原始值"""
        risks = []
        inference_patterns = [
            re.compile(r"(?:猜测|推断|可能|大概是|应该是|似乎是).*?是.*?(?:PERSON|COMPANY|AMOUNT|ID_CARD|PHONE|BANK_CARD)_\w+"),
            re.compile(r"(?:PERSON|COMPANY|AMOUNT|ID_CARD|PHONE|BANK_CARD)_\w+.*?(?:可能是|可能是|应该是|大概是)\s*[\u4e00-\u9fa5]+")
        ]
        
        for pattern in inference_patterns:
            for match in pattern.finditer(text):
                risks.append(ValidationRisk(
                    risk_type="ENTITY_INFERENCE_ATTEMPT",
                    level=ValidationRiskLevel.HIGH,
                    description="LLM试图推断脱敏实体的原始值",
                    evidence=match.group(),
                    position=(match.start(), match.end())
                ))
        
        return risks
    
    def _find_position(self, text: str, target: str) -> Optional[Tuple[int, int]]:
        """查找目标字符串在文本中的位置"""
        idx = text.find(target)
        if idx >= 0:
            return (idx, idx + len(target))
        return None
```

### 7.3 LLM编造/幻觉检测

```python
class HallucinationDetector:
    """
    LLM编造/幻觉检测器
    
    检测minimax-m3返回内容中是否包含：
    1. 不在原始上下文中的"事实"
    2. 与上下文矛盾的陈述
    3. 过度推断的内容
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.similarity_threshold = config.get("similarity_threshold", 0.3)
    
    def detect(
        self,
        response_text: str,
        source_chunks: List[str]
    ) -> List[ValidationRisk]:
        """
        检测幻觉内容
        
        策略：
        1. 将响应拆分为事实性陈述句
        2. 每句与原始Chunk进行相似度/包含性检查
        3. 标记无法溯源的陈述
        """
        risks = []
        
        # 拆分事实陈述
        statements = self._extract_statements(response_text)
        
        for stmt in statements:
            # 跳过引用标记和元信息
            if self._is_meta_statement(stmt):
                continue
            
            # 检查是否能在原始上下文中找到支撑
            supported, evidence = self._check_statement_support(stmt, source_chunks)
            
            if not supported:
                risks.append(ValidationRisk(
                    risk_type="POTENTIAL_HALLUCINATION",
                    level=ValidationRiskLevel.MEDIUM,
                    description="陈述缺乏原始上下文支撑",
                    evidence=f"陈述: {stmt[:50]}..."
                ))
        
        return risks
    
    def _extract_statements(self, text: str) -> List[str]:
        """提取事实性陈述句"""
        # 按句子拆分（简化版）
        sentences = re.split(r'[。！？\n]', text)
        statements = []
        for s in sentences:
            s = s.strip()
            if len(s) > 10 and not s.startswith("["):
                statements.append(s)
        return statements
    
    def _is_meta_statement(self, stmt: str) -> bool:
        """判断是否为元信息陈述（如"根据上下文"、"综上所述"等）"""
        meta_prefixes = [
            "根据", "综上所述", "总之", "因此", "所以",
            "以上是", "请注意", "需要说明的是"
        ]
        return any(stmt.startswith(prefix) for prefix in meta_prefixes)
    
    def _check_statement_support(
        self,
        statement: str,
        source_chunks: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        检查陈述是否在原始上下文中有支撑
        
        简化实现：检查陈述的关键短语是否出现在任一Chunk中
        """
        # 提取关键短语（去掉停用词后的名词短语）
        key_phrases = self._extract_key_phrases(statement)
        
        if not key_phrases:
            return True, None  # 无关键短语，跳过
        
        for chunk in source_chunks:
            chunk_text = chunk if isinstance(chunk, str) else chunk.get("content", "")
            match_count = sum(1 for phrase in key_phrases if phrase in chunk_text)
            match_ratio = match_count / len(key_phrases)
            
            if match_ratio >= self.similarity_threshold:
                return True, chunk_text[:100]
        
        return False, None
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """提取关键短语"""
        # 简化实现：提取长度>=2的词组
        words = re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}', text)
        # 过滤常见停用词
        stopwords = {"根据", "所述", "可以", "进行", "需要", "如果", "是否", "以及"}
        return [w for w in words if w not in stopwords]


# 自定义异常
class ResponseValidationException(Exception):
    """响应校验异常"""
    def __init__(self, message: str, risks: List[ValidationRisk] = None):
        super().__init__(message)
        self.risks = risks or []


# 在 Gateway 中的集成
async def _step9_validate_response(
    self,
    raw_response: str,
    entity_mapping: List[EntityMaskMapping]
) -> Tuple[str, List[ValidationRisk]]:
    """Step 9: 返回校验"""
    all_risks = []
    
    # 1. 关键词拦截
    intercepted_text, keyword_risks = self.response_validator.keyword_interceptor.intercept(
        raw_response, entity_mapping
    )
    all_risks.extend(keyword_risks)
    
    # 2. 幻觉检测
    # 获取原始Chunk文本用于对比
    source_chunks = [m.original for m in entity_mapping]  # 简化
    hallucination_risks = self.response_validator.hallucination_detector.detect(
        intercepted_text, source_chunks
    )
    all_risks.extend(hallucination_risks)
    
    return intercepted_text, all_risks
```

---

## 8. 审计日志设计

### 8.1 审计日志Schema

```sql
-- API安全网关审计日志表
CREATE TABLE api_security_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 请求标识
    request_id VARCHAR(64) NOT NULL UNIQUE,
    trace_id VARCHAR(64),                    -- 分布式追踪ID
    
    -- 请求信息
    query_text TEXT,                         -- 用户原始查询（可选脱敏存储）
    task_type VARCHAR(50) NOT NULL,          -- 任务类型
    user_id UUID REFERENCES users(id),
    role_id UUID REFERENCES roles(id),
    department_id UUID REFERENCES departments(id),
    
    -- 安全评估结果
    max_security_level VARCHAR(20) NOT NULL, -- L0/L1/L2/L3/L4
    processing_strategy VARCHAR(30) NOT NULL, -- local_only / entity_masking / direct_with_compression
    
    -- 内容统计
    input_chunk_count INTEGER DEFAULT 0,     -- 输入Chunk数
    masked_entity_count INTEGER DEFAULT 0,   -- 脱敏实体数
    compressed_token_count INTEGER,          -- 压缩后Token数
    original_token_count INTEGER,            -- 原始Token数
    
    -- API调用信息
    api_called BOOLEAN DEFAULT FALSE,        -- 是否调用了外部API
    api_provider VARCHAR(50),                -- API提供商
    api_request_size_bytes INTEGER,          -- 请求体大小
    api_response_size_bytes INTEGER,         -- 响应体大小
    api_latency_ms INTEGER,                  -- API调用耗时
    api_status_code INTEGER,                 -- HTTP状态码
    
    -- 返回校验
    validation_risks JSONB DEFAULT '[]',     -- 发现的风险列表
    risk_count INTEGER DEFAULT 0,            -- 风险数量
    critical_risk_count INTEGER DEFAULT 0,   -- 严重风险数量
    
    -- 处理结果
    response_hash VARCHAR(64),               -- 响应内容哈希（用于完整性校验）
    audit_status VARCHAR(20) NOT NULL,       -- completed / failed / blocked
    error_message TEXT,                      -- 错误信息
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- 索引
    INDEX idx_audit_user_id (user_id),
    INDEX idx_audit_created_at (created_at),
    INDEX idx_audit_max_level (max_security_level),
    INDEX idx_audit_strategy (processing_strategy),
    INDEX idx_audit_status (audit_status)
);

-- 审计日志详情表（存储完整的处理步骤）
CREATE TABLE api_security_audit_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_log_id UUID REFERENCES api_security_audit_logs(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    step_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,             -- completed / failed / skipped / warning
    input_summary TEXT,                      -- 步骤输入摘要（脱敏）
    output_summary TEXT,                     -- 步骤输出摘要（脱敏）
    processing_time_ms INTEGER,
    metadata JSONB DEFAULT '{}',             -- 步骤级元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(audit_log_id, step_number)
);

-- 实体脱敏映射审计表（用于事后审计和合规检查）
CREATE TABLE api_security_entity_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_log_id UUID REFERENCES api_security_audit_logs(id) ON DELETE CASCADE,
    placeholder VARCHAR(64) NOT NULL,        -- 占位符
    entity_type VARCHAR(30) NOT NULL,        -- 实体类型
    original_hash VARCHAR(64) NOT NULL,      -- 原始值的SHA256哈希（不存明文）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 8.2 审计日志记录实现

```python
# services/security/audit_logger.py

import json
import hashlib
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass


class AuditLogger:
    """
    API安全审计日志记录器
    
    记录每次API调用的完整安全审计信息，
    支持同步和异步写入，确保审计日志不丢失。
    """
    
    def __init__(self, db_client, async_queue=None):
        self.db = db_client
        self.queue = async_queue  # 可选：消息队列（如RabbitMQ）用于异步写入
    
    async def log(
        self,
        request_id: str,
        audit_payload: Dict,
        final_response: str,
        processing_time_ms: int,
        user_context: Optional[Dict] = None
    ) -> str:
        """
        记录安全审计日志
        
        Args:
            request_id: 请求ID
            audit_payload: 审计负载（包含所有处理步骤）
            final_response: 最终响应文本
            processing_time_ms: 总处理耗时
            user_context: 用户上下文
        
        Returns:
            audit_log_id: 审计日志记录ID
        """
        # 提取关键字段
        steps = audit_payload.get("steps", [])
        max_level = self._extract_max_level(steps)
        strategy = self._extract_strategy(steps)
        api_called = self._extract_api_called(steps)
        entity_count = self._extract_entity_count(steps)
        risks = self._extract_risks(steps)
        
        # 计算响应哈希
        response_hash = hashlib.sha256(final_response.encode()).hexdigest()
        
        # 构建主记录
        audit_record = {
            "request_id": request_id,
            "trace_id": audit_payload.get("trace_id"),
            "query_text": self._mask_query_for_audit(audit_payload.get("query", "")),
            "task_type": audit_payload.get("task_type", "unknown"),
            "user_id": user_context.get("user_id") if user_context else None,
            "role_id": user_context.get("role_id") if user_context else None,
            "department_id": user_context.get("department_id") if user_context else None,
            "max_security_level": max_level,
            "processing_strategy": strategy,
            "input_chunk_count": self._extract_chunk_count(steps),
            "masked_entity_count": entity_count,
            "api_called": api_called,
            "api_provider": "minimax-m3" if api_called else None,
            "validation_risks": json.dumps(risks),
            "risk_count": len(risks),
            "critical_risk_count": sum(1 for r in risks if r.get("level") == "critical"),
            "response_hash": response_hash,
            "audit_status": audit_payload.get("status", "completed"),
            "error_message": audit_payload.get("error"),
            "processing_time_ms": processing_time_ms,
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
        }
        
        # 异步写入数据库
        audit_log_id = await self._persist_audit_record(audit_record)
        
        # 异步写入步骤详情
        await self._persist_audit_steps(audit_log_id, steps)
        
        # 如果使用了实体脱敏，记录映射哈希
        entity_mappings = audit_payload.get("entity_mappings", [])
        if entity_mappings:
            await self._persist_entity_mappings(audit_log_id, entity_mappings)
        
        # 发送到消息队列（用于实时审计监控）
        if self.queue:
            await self.queue.publish("audit.security", {
                "event": "api_security_gateway_completed",
                "request_id": request_id,
                "audit_log_id": str(audit_log_id),
                "max_level": max_level,
                "strategy": strategy,
                "risk_count": len(risks),
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return str(audit_log_id)
    
    def _mask_query_for_audit(self, query: str) -> str:
        """对审计日志中的查询进行轻度脱敏"""
        # 移除可能的敏感信息（身份证号、手机号等）
        query = re.sub(r"\d{17}[\dXx]", "[ID_CARD_REDACTED]", query)
        query = re.sub(r"1[3-9]\d{9}", "[PHONE_REDACTED]", query)
        return query
    
    def _extract_max_level(self, steps: List[Dict]) -> str:
        """从步骤中提取最高安全等级"""
        for step in steps:
            if step.get("name") == "security_assessment":
                return step.get("max_level", "UNKNOWN")
        return "UNKNOWN"
    
    def _extract_strategy(self, steps: List[Dict]) -> str:
        """从步骤中提取处理策略"""
        for step in steps:
            if step.get("name") == "strategy_selection":
                return step.get("strategy", "unknown")
        return "unknown"
    
    def _extract_api_called(self, steps: List[Dict]) -> bool:
        """判断是否调用了API"""
        for step in steps:
            if step.get("name") == "api_call":
                return step.get("status") == "completed"
        return False
    
    def _extract_entity_count(self, steps: List[Dict]) -> int:
        """提取脱敏实体数量"""
        for step in steps:
            if step.get("name") == "entity_masking":
                return step.get("masked_entities_count", 0)
        return 0
    
    def _extract_risks(self, steps: List[Dict]) -> List[Dict]:
        """提取发现的风险"""
        for step in steps:
            if step.get("name") == "response_validation":
                return step.get("risks_found", [])
        return []
    
    def _extract_chunk_count(self, steps: List[Dict]) -> int:
        """提取输入Chunk数量"""
        for step in steps:
            if step.get("name") == "retrieval":
                return step.get("input_chunk_count", 0)
        return 0
    
    async def _persist_audit_record(self, record: Dict) -> str:
        """持久化审计主记录"""
        # 使用SQLAlchemy或原始SQL写入
        # 简化示意：
        query = """
            INSERT INTO api_security_audit_logs (
                request_id, trace_id, query_text, task_type, user_id, role_id,
                department_id, max_security_level, processing_strategy,
                input_chunk_count, masked_entity_count, api_called, api_provider,
                validation_risks, risk_count, critical_risk_count,
                response_hash, audit_status, error_message,
                processing_time_ms, created_at, completed_at
            ) VALUES (
                :request_id, :trace_id, :query_text, :task_type, :user_id, :role_id,
                :department_id, :max_security_level, :processing_strategy,
                :input_chunk_count, :masked_entity_count, :api_called, :api_provider,
                :validation_risks, :risk_count, :critical_risk_count,
                :response_hash, :audit_status, :error_message,
                :processing_time_ms, :created_at, :completed_at
            ) RETURNING id
        """
        result = await self.db.execute(query, record)
        return result.scalar()
    
    async def _persist_audit_steps(self, audit_log_id: str, steps: List[Dict]):
        """持久化审计步骤详情"""
        for step in steps:
            record = {
                "audit_log_id": audit_log_id,
                "step_number": step.get("step", 0),
                "step_name": step.get("name", ""),
                "status": step.get("status", ""),
                "metadata": json.dumps({k: v for k, v in step.items() 
                                       if k not in ["step", "name", "status"]}),
                "created_at": datetime.utcnow()
            }
            await self.db.execute("""
                INSERT INTO api_security_audit_steps 
                (audit_log_id, step_number, step_name, status, metadata, created_at)
                VALUES (:audit_log_id, :step_number, :step_name, :status, :metadata, :created_at)
            """, record)
    
    async def _persist_entity_mappings(
        self, 
        audit_log_id: str, 
        mappings: List[Dict]
    ):
        """持久化实体映射（仅存储哈希，不存明文）"""
        for mapping in mappings:
            original_hash = hashlib.sha256(
                mapping["original"].encode()
            ).hexdigest()
            record = {
                "audit_log_id": audit_log_id,
                "placeholder": mapping["placeholder"],
                "entity_type": mapping["entity_type"],
                "original_hash": original_hash,
                "created_at": datetime.utcnow()
            }
            await self.db.execute("""
                INSERT INTO api_security_entity_mappings
                (audit_log_id, placeholder, entity_type, original_hash, created_at)
                VALUES (:audit_log_id, :placeholder, :entity_type, :original_hash, :created_at)
            """, record)
```

### 8.3 审计日志查询示例

```sql
-- 查询某用户最近的高风险API调用
SELECT 
    request_id,
    max_security_level,
    processing_strategy,
    risk_count,
    critical_risk_count,
    api_called,
    processing_time_ms,
    created_at
FROM api_security_audit_logs
WHERE user_id = 'user_uuid_here'
  AND max_security_level IN ('CONFIDENTIAL', 'TOP_SECRET')
ORDER BY created_at DESC
LIMIT 50;

-- 统计各安全等级的调用分布
SELECT 
    max_security_level,
    processing_strategy,
    COUNT(*) as call_count,
    AVG(processing_time_ms) as avg_time_ms,
    SUM(CASE WHEN api_called THEN 1 ELSE 0 END) as api_call_count,
    SUM(risk_count) as total_risks
FROM api_security_audit_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY max_security_level, processing_strategy
ORDER BY max_security_level DESC;

-- 发现实体脱敏还原的安全事件
SELECT 
    a.request_id,
    a.user_id,
    a.created_at,
    s.metadata as step_details
FROM api_security_audit_logs a
JOIN api_security_audit_steps s ON a.id = s.audit_log_id
WHERE s.step_name = 'response_validation'
  AND s.status = 'warning'
  AND a.created_at >= NOW() - INTERVAL '24 hours';
```

---

## 9. 脱敏还原策略

### 9.1 还原流程

```
minimax-m3返回的脱敏响应
       │
       v
┌──────────────────┐
│ 提取占位符       │
│ <TYPE_HASH> 格式 │
└──────────────────┘
       │
       v
┌──────────────────┐
│ 查找映射表       │
│ placeholder →    │
│ original         │
└──────────────────┘
       │
       v
┌──────────────────┐
│ 一致性校验       │
│ 占位符上下文     │
│ 是否匹配原始值   │
└──────────────────┘
       │
       v
┌──────────────────┐
│ 执行还原替换     │
│ 逐占位符还原     │
└──────────────────┘
       │
       v
  最终响应（含明文）
```

### 9.2 脱敏还原器实现

```python
# services/security/entity_unmasker.py

import re
from typing import List, Dict, Tuple
from dataclasses import dataclass


class EntityUnmasker:
    """
    实体脱敏还原器
    
    将minimax-m3返回响应中的占位符还原为原始实体值。
    支持一致性校验，防止还原错误。
    """
    
    PLACEHOLDER_PATTERN = re.compile(r"<([A-Z_]+)_([0-9A-F]{4})>")
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.enable_consistency_check = config.get("enable_consistency_check", True)
    
    def unmask(
        self,
        response_text: str,
        entity_mapping: List[EntityMaskMapping]
    ) -> str:
        """
        还原响应中的占位符
        
        Args:
            response_text: minimax-m3返回的文本（含占位符）
            entity_mapping: 实体脱敏映射表
        
        Returns:
            还原后的文本
        """
        # 构建占位符到原始值的快速查找映射
        mapping_dict: Dict[str, str] = {}
        placeholder_meta: Dict[str, Dict] = {}
        
        for m in entity_mapping:
            mapping_dict[m.placeholder] = m.original
            placeholder_meta[m.placeholder] = {
                "type": m.entity_type,
                "original": m.original
            }
        
        # 从后往前替换，避免位置偏移
        result = response_text
        matches = list(self.PLACEHOLDER_PATTERN.finditer(response_text))
        
        for match in reversed(matches):
            placeholder = match.group()
            original = mapping_dict.get(placeholder)
            
            if original is None:
                # 未知占位符：保留原样并记录警告
                continue
            
            # 一致性校验（可选）
            if self.enable_consistency_check:
                is_consistent = self._check_context_consistency(
                    result, match.start(), match.end(),
                    placeholder, original, placeholder_meta[placeholder]["type"]
                )
                if not is_consistent:
                    # 上下文不一致，保留占位符
                    continue
            
            # 执行还原
            result = result[:match.start()] + original + result[match.end():]
        
        return result
    
    def _check_context_consistency(
        self,
        text: str,
        placeholder_start: int,
        placeholder_end: int,
        placeholder: str,
        original: str,
        entity_type: str
    ) -> bool:
        """
        检查占位符还原是否与上下文一致
        
        校验逻辑：
        1. 如果占位符前是动词"联系了"、"致电"，原始值应该是联系方式
        2. 如果占位符在"公司"前，原始值应该是公司名
        """
        # 获取上下文窗口
        window_size = 20
        prefix = text[max(0, placeholder_start - window_size):placeholder_start]
        suffix = text[placeholder_end:placeholder_end + window_size]
        
        # 类型一致性检查
        type_hints = {
            "phone": ["手机", "电话", "拨打", "联系", "致电"],
            "email": ["邮箱", "邮件", "发信", "Email"],
            "person_name": ["经理", "总监", "先生", "女士", "总裁", "CEO"],
            "company_name": ["公司", "集团", "企业", "与", "和"],
            "amount": ["金额", "费用", "成本", "预算", "投入", "融资"],
            "id_card": ["身份证", "证件号", "号码"],
        }
        
        hints = type_hints.get(entity_type, [])
        context = prefix + suffix
        
        # 如果有类型提示词，检查是否出现在上下文中
        if hints:
            has_hint = any(h in context for h in hints)
            # 如果没有提示词，不一定是错误，但记录低置信度
            return True  # 简化：始终通过，复杂场景可扩展
        
        return True
    
    def unmask_structured(
        self,
        response_data: Dict,
        entity_mapping: List[EntityMaskMapping]
    ) -> Dict:
        """
        还原结构化响应（JSON/Dict）中的所有占位符
        
        递归遍历Dict中的所有字符串值进行还原。
        """
        mapping_dict = {m.placeholder: m.original for m in entity_mapping}
        
        def _recursive_unmask(obj):
            if isinstance(obj, str):
                return self._unmask_string(obj, mapping_dict)
            elif isinstance(obj, dict):
                return {k: _recursive_unmask(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_recursive_unmask(item) for item in obj]
            else:
                return obj
        
        return _recursive_unmask(response_data)
    
    def _unmask_string(self, text: str, mapping_dict: Dict[str, str]) -> str:
        """还原字符串中的所有占位符"""
        result = text
        for placeholder, original in mapping_dict.items():
            result = result.replace(placeholder, original)
        return result
```

### 9.3 脱敏还原示例

| 阶段 | 内容 |
|------|------|
| **minimax-m3返回** | `<PERSON_A3F2>`在发布会上透露，公司明年计划进军海外市场，预计初期投入`<AMOUNT_7B1C>`。与`<COMPANY_C1D8>`的合作协议已签署，合同金额为`<AMOUNT_3F7A>`。 |
| **映射表** | PERSON_A3F2→张三, AMOUNT_7B1C→5000万元, COMPANY_C1D8→蓝海科技集团, AMOUNT_3F7A→2亿元 |
| **还原后** | 张三在发布会上透露，公司明年计划进军海外市场，预计初期投入5000万元。与蓝海科技集团的合作协议已签署，合同金额为2亿元。 |

### 9.4 安全注意事项

```python
# 脱敏还原的安全约束

UNMASKING_SAFETY_RULES = {
    # 1. 还原操作仅在系统内部执行，不记录还原后的完整响应到审计日志
    "audit_storage": "只存储response_hash，不存储明文",
    
    # 2. 还原后的响应仅在当前请求会话中保留，不进入缓存
    "caching_policy": "还原后的响应禁止进入任何缓存层（Redis/Milvus等）",
    
    # 3. 日志中占位符的原始值用哈希存储，不可逆
    "mapping_storage": "entity_mappings表只存original_hash，不存original明文",
    
    # 4. 映射表的生命周期管理
    "mapping_ttl": "请求结束后，内存中的映射表应立即清理（TTL=0）",
    
    # 5. 批量还原的速率限制
    "rate_limit": "单个请求最多还原100个占位符，防止异常请求",
    
    # 6. 权限二次校验
    "permission_recheck": "还原前再次校验用户是否有权查看该安全等级的原始内容",
}
```

---

## 附录A：配置汇总

```yaml
# config/api_security_gateway.yaml

api_security_gateway:
  # 安全等级阈值
  level_thresholds:
    top_secret: 0.85
    confidential: 0.60
    internal: 0.30
    public: 0.0
  
  # 处理策略配置
  strategies:
    top_secret:
      action: "local_only"
      local_llm_enabled: true
      local_llm_endpoint: "http://localhost:8080/v1/chat"
    
    confidential:
      action: "entity_masking"
      masking_strategy: "placeholder"
      preserve_structure: true
    
    internal:
      action: "direct_with_compression"
      compression_budget_tokens: 2048
    
    public:
      action: "direct"
      compression_budget_tokens: null  # 无限制
  
  # 实体脱敏配置
  entity_masking:
    enabled_types:
      - person_name
      - company_name
      - id_card
      - phone
      - bank_card
      - email
      - amount
    placeholder_prefix:
      person_name: "PERSON"
      company_name: "COMPANY"
      id_card: "ID_CARD"
      phone: "PHONE"
      bank_card: "BANK_CARD"
      email: "EMAIL"
      amount: "AMOUNT"
    consistent_mapping_ttl_seconds: 3600
  
  # 返回校验配置
  response_validation:
    keyword_interceptor:
      enabled: true
      custom_blacklist: []
    
    hallucination_detector:
      enabled: true
      similarity_threshold: 0.3
    
    safety_scanner:
      enabled: true
  
  # 审计日志配置
  audit_logging:
    enabled: true
    async_queue: "rabbitmq"
    retention_days: 365
    mask_query_in_audit: true
    store_entity_hashes_only: true
  
  # API客户端配置
  api_client:
    provider: "minimax-m3"
    base_url: "https://api.minimaxi.com/v1"
    timeout_seconds: 30
    max_retries: 3
    circuit_breaker:
      failure_threshold: 5
      recovery_timeout_seconds: 60
```

---

## 附录B：错误码定义

| 错误码 | 含义 | 触发场景 | 处理建议 |
|--------|------|----------|----------|
| `ASG-001` | 内容安全评估失败 | 安全评估器内部错误 | 降级为L4本地处理 |
| `ASG-002` | 绝密内容阻断 | 检测到L4级内容 | 提示用户使用本地模型 |
| `ASG-003` | 实体脱敏失败 | NER引擎异常 | 阻断API调用 |
| `ASG-004` | API调用超时 | minimax-m3响应超时 | 重试或降级 |
| `ASG-005` | 返回校验阻断 | 检测到严重安全风险 | 返回安全提示，不暴露原始响应 |
| `ASG-006` | 实体还原失败 | 映射表缺失或损坏 | 返回占位符版本，记录异常 |
| `ASG-007` | 熔断触发 | API连续失败次数超限 | 临时切换本地模型 |
| `ASG-008` | 审计日志写入失败 | 数据库/队列异常 | 记录到本地文件，稍后补录 |

---

> **文档结束**
>
> 本文档为企业级私有化多模态RAG系统调用外部API时的安全控制方案，
> 所有实现代码为设计示意，实际开发中需根据具体业务场景和minimax-m3
> API规范进行调整。
