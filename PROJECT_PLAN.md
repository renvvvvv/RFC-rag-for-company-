# 企业级私有化多模态RAG系统 — 项目搭建实施计划

> 版本: v1.0 | 日期: 2026-06-10

---

## 项目目标

将 `docs/design/` 中的15份方案文档转化为可运行的代码项目，优先完成 **MVP核心版**（Phase 1）。

---

## 批次计划

### 第一批：基础环境搭建（3个agent并行）

| Agent | 任务 | 输出文件 |
|-------|------|----------|
| A | Docker Compose + Kong + 监控配置 | `docker-compose.yml`, `kong.yml`, `monitoring/prometheus.yml`, `monitoring/grafana/*` |
| B | FastAPI后端基础框架 | `backend/main.py`, `config.py`, `database.py`, `core/exceptions.py`, `requirements.txt`, `Dockerfile`, `Dockerfile.worker` |
| C | React前端基础框架 | `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `src/App.tsx`, `src/main.tsx`, `src/router.tsx`, `src/layout/*`, `src/services/api.ts` |

### 第二批：数据层与存储（3个agent并行）

| Agent | 任务 | 输出文件 |
|-------|------|----------|
| D | PostgreSQL数据模型 + Alembic迁移 | `backend/app/models/*.py`, `backend/alembic/*`, 生成初始迁移脚本 |
| E | Milvus向量存储封装 | `backend/app/retrieval/vector_store.py`, `backend/app/retrieval/milvus_client.py` |
| F | Redis缓存封装 | `backend/app/core/cache.py`, `backend/app/core/redis_client.py` |

### 第三批：核心服务（3个agent并行）

| Agent | 任务 | 输出文件 |
|-------|------|----------|
| G | 用户群与权限服务 | `backend/app/services/permission_service.py`, `backend/app/services/auth_service.py`, `backend/app/api/v1/permission.py`, `backend/app/api/v1/group.py` |
| H | 关键词敏感控制服务 | `backend/app/services/keyword_service.py`, `backend/app/pipelines/keyword_annotator.py`, `backend/app/api/v1/keyword.py` |
| I | 文档摄取Pipeline | `backend/app/pipelines/*.py`, `backend/app/services/document_service.py`, `backend/app/workers/ingest_tasks.py`, `backend/app/api/v1/document.py` |

### 第四批：检索与生成（3个agent并行）

| Agent | 任务 | 输出文件 |
|-------|------|----------|
| J | 检索与重排序引擎 | `backend/app/retrieval/retriever.py`, `backend/app/retrieval/fusion.py`, `backend/app/retrieval/reranker.py`, `backend/app/api/v1/search.py` |
| K | API安全网关 + 上下文压缩 | `backend/app/security/api_gateway.py`, `backend/app/security/compressor.py`, `backend/app/security/validator.py` |
| L | 生成服务 + 问答API | `backend/app/services/chat_service.py`, `backend/app/api/v1/chat.py`, `backend/app/services/eval_service.py`, `backend/app/api/v1/eval.py` |

### 第五批：前端与集成（2个agent并行）

| Agent | 任务 | 输出文件 |
|-------|------|----------|
| M | 前端页面（上传/知识库/检索） | `frontend/src/pages/*.tsx`, `frontend/src/components/UploadPanel/*.tsx`, `frontend/src/components/DocViewer/*.tsx` |
| N | 前端页面（权限/评测） | `frontend/src/components/PermissionEditor/*.tsx`, `frontend/src/components/TagManager/*.tsx`, `frontend/src/components/EvalDashboard/*.tsx`, `frontend/src/pages/PermissionMgr.tsx`, `frontend/src/pages/EvalWorkbench.tsx` |

### 第六批：整合测试与验证

- 修复模块间接口不一致问题
- 编写集成测试
- 验证Docker Compose可以一键启动
- 验证基础API可访问

---

## 接口约定

### 后端模块接口

```python
# 权限服务 (backend/app/services/permission_service.py)
class PermissionService:
    async def get_user_effective_permissions(self, user_id: str) -> EffectivePermission
    async def check_document_permission(self, user_id: str, doc_id: str) -> PermissionResult
    async def check_field_permission(self, user_id: str, chunk: Chunk) -> bool
    async def get_user_security_level(self, user_id: str) -> str  # L0-L4

# 关键词服务 (backend/app/services/keyword_service.py)
class KeywordService:
    async def annotate_chunk(self, chunk: Chunk) -> Chunk
    async def check_content_level(self, text: str, user_level: str) -> KeywordCheckResult
    async def intercept_response(self, answer: str, context_chunks: List[Chunk], user_id: str) -> InterceptResult

# 检索服务 (backend/app/services/search_service.py)
class SearchService:
    async def search(self, query: str, user_id: str, kb_ids: List[str], top_k: int) -> SearchResult

# 聊天服务 (backend/app/services/chat_service.py)
class ChatService:
    async def chat(self, query: str, user_id: str, kb_ids: List[str], stream: bool = False) -> ChatResponse
```

### 环境变量

```bash
# 数据库
DATABASE_URL=postgresql://rag_user:rag_password@postgres:5432/rag_kb

# Redis
REDIS_URL=redis://redis:6379/0

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/

# Milvus
MILVUS_HOST=milvus-standalone
MILVUS_PORT=19530

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=rag-documents

# 模型配置（用户提供）
EMBEDDING_MODEL_URL=http://embedding-service:8080
RERANK_MODEL_URL=http://rerank-service:8080
MINIMAX_API_KEY=sk-xxx
MINIMAX_API_BASE=https://api.minimaxi.chat/v1

# 安全
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

## 完成标准

1. `docker-compose up -d` 可以一键启动所有服务
2. `http://localhost:8000/docs` 可以访问FastAPI自动生成的API文档
3. `http://localhost:3000` 可以访问前端页面
4. 可以完成：上传文档 → 解析分块 → 向量化 → 检索 → 问答 的完整流程
5. 权限控制和关键词拦截功能可演示
