# 企业级私有 RAG 轻量化 / 全量化双模式部署方案

> 目标：在保留“权限 RAG 管理系统”核心特色的前提下，提供 **轻量化（Lightweight）** 与 **全量化（Full）** 两种部署形态。
> 文档日期：2026-06-24

---

## 1. 现状问题

当前默认 Docker Compose 栈即使经过第一轮优化，仍然是“全量化”思路：

| 指标 | 当前值 |
|------|--------|
| 容器数 | 14（默认）/ 17（含监控） |
| 镜像下载 | ~10 GB |
| 建议内存 | 16 GiB |
| 建议 CPU | 16 核 |

对于只想体验“权限 RAG 管理”核心功能（用户分级、知识库管理、文档上传、权限检索、安全网关）的场景，这个 footprint 仍然过重。

---

## 2. 核心特色拆解

必须保留的“权限 RAG 管理系统”能力：

1. **分级用户体系**：L0–L4 安全级别、角色、用户组
2. **知识库管理**：创建、授权、公开/私有、组成员访问
3. **文档上传与解析**：PDF/Word/Excel/图片等，含 OCR
4. **向量化与检索**：支持语义搜索 + 关键词搜索
5. **权限过滤**：检索时按用户级别、KB 权限、文档 ACL 过滤
6. **安全网关（Security Gateway）**：根据查询内容级别拦截外部 API
7. **API Key 外部认证**：按 scope 授权、限流
8. **RAG Chat**：带溯源的回答生成

可以按需裁剪的非核心基础设施：

- Milvus（可用 pgvector 替代）
- MinIO（可用本地文件系统替代）
- RabbitMQ（可用 Redis 做 Celery broker）
- Kong（轻量模式可直接暴露后端）
- 独立 Worker 容器（轻量模式后端同步处理）
- Prometheus/Grafana（本来就是可选）
- 独立 embedding-service / llm-service（本来就是 mock/可选）

---

## 3. 双模式设计

### 3.1 轻量化模式（Lightweight）

**设计哲学**：单机能跑、镜像小、启动快、保留全部权限 RAG 核心功能。

```
┌────────────────────────────────────────────────────────┐
│  容器 1: rag-lw-frontend  (React + nginx)              │
│  容器 2: rag-lw-app-backend  (FastAPI)                 │
│  容器 3: rag-lw-worker  (Celery: ingest/embed/permission) │
│  容器 4: rag-lw-postgres  (关系库 + pgvector)          │
│  容器 5: rag-lw-redis  (缓存 + Celery broker)          │
└────────────────────────────────────────────────────────┘
```

> 注：worker 负责异步文档解析和向量化，避免大文件上传阻塞 API。若希望极致精简到 4 容器，可设置 `CELERY_TASK_ALWAYS_EAGER=true` 并让后端同步处理，但不建议用于生产或复杂文档。

**技术替代**：

| 全量化组件 | 轻量化替代 | 说明 |
|-----------|-----------|------|
| Milvus | PostgreSQL + `pgvector` 扩展 | 向量存储在 Postgres，权限过滤用 SQL |
| MinIO | 本地文件系统 `/app/data/documents` | 简化文件存储 |
| RabbitMQ | Redis | Celery broker 改为 Redis |
| 3 个 Worker | 后端进程内同步 / 后台线程 | 小文档量时直接处理 |
| Kong | 可选，默认直连 `backend:8080` | 前端 nginx 直接反代后端 |
| 监控 | 不启动 | 本就可选 |
| embedding-service / llm-service | 外部 API | 配置 `EMBEDDING_API_URL` / `LLM_API_URL` |

**预期资源**：

| 指标 | 估算 |
|------|------|
| 容器数 | **5** |
| 镜像下载 | **~2.8 GB** |
| 运行时内存 | **4–5 GiB** |
| 建议 CPU | **4 核** |
| 启动时间 | < 90 秒 |
| Compose 文件 | `docker-compose.lightweight.yml` |

**适用场景**：

- 本地开发 / 个人 POC
- 小企业内网部署（< 50 人）
- 演示环境
- 文档量 < 10 万

---

### 3.2 全量化模式（Full）

**设计哲学**：当前优化后的完整架构，适合生产横向扩展。

```
┌─────────────────────────────────────────────────────────────┐
│  接入层：Kong                                                 │
│  应用层：backend + frontend + 3 Workers                       │
│  模型层：embedding-service + llm-service（或外部 API）         │
│  数据层：Postgres + Redis + RabbitMQ + Milvus + etcd + MinIO │
│  可观测：Prometheus + Grafana + Alertmanager（可选）          │
└─────────────────────────────────────────────────────────────┘
```

**预期资源**：

| 指标 | 估算 |
|------|------|
| 容器数 | 14 / 17（含监控） |
| 镜像下载 | ~10 / ~11 GB |
| 运行时内存 | 10–16 GiB |
| 建议 CPU | 8–16 核 |

**适用场景**：

- 中大型企业生产
- 高并发检索
- 文档量 > 10 万
- 需要独立扩展 Worker / Milvus

---

## 4. 进一步压缩空间分析

即使轻量化后，仍可继续压缩：

### 4.1 拆分包依赖（最大收益）

当前后端镜像 1.63 GB 中，Python 依赖仍占 ~900 MB（`unstructured` + `spacy` + `llvmlite` + `pandas` 等）。

| 拆分方案 | 预计镜像大小 | 说明 |
|---------|------------|------|
| backend 不装 `unstructured` | **~700 MB** | API 层不需要文档解析 |
| ingest 单独 requirements | **~1.6 GB** | 只保留解析相关依赖 |
| 使用 alpine 基础镜像 | 再 **-100–200 MB** | 但编译依赖更复杂 |

### 4.2 去掉 meilisearch 依赖

当前 `requirements.txt` 包含 `meilisearch`，但代码中 `meilisearch_store` 已经做了 graceful degrade。如果只做 pgvector + 简单 SQL 关键词搜索，可以移除该依赖，再减几十 MB。

### 4.3 使用 pgvector 替代 Milvus

Milvus 镜像 2.28 GB，pgvector 只是 Postgres 的一个扩展（在 `postgres:16` 镜像上安装增加 <100 MB）。仅此一项可减 **~2 GB** 镜像和 **~2 GB** 运行时内存上限。

### 4.4 使用 Redis 替代 RabbitMQ

RabbitMQ 镜像 392 MB，Redis 仅 58 MB。Celery 对 Redis broker 支持成熟。

### 4.5 使用本地文件系统替代 MinIO

MinIO 镜像 220 MB，本地存储零额外镜像。但丧失 S3 兼容性和分布式能力。

### 4.6 极限压缩估算

如果只做最核心功能（用户 + KB + 文档 + pgvector 检索 + 安全网关），极限可压到：

| 指标 | 估算 |
|------|------|
| 镜像下载 | **~1.5 GB** |
| 运行时内存 | **2 GiB** |
| CPU | **2 核** |

但这需要：
- 后端只保留 API/DB/缓存依赖
- 文档解析改为外部服务或异步队列不常驻
- 向量检索仅 pgvector
- 文件存储本地

---

## 5. 实施路线图

### Phase 1：存储层解耦（1–2 天）

1. **文件存储抽象**
   - 创建 `app/storage/base.py`：`BaseStorage` 接口
   - 创建 `app/storage/local.py`：本地文件系统实现
   - 创建 `app/storage/s3.py`：兼容 MinIO/S3 实现
   - `DocumentService` 改为根据 `STORAGE_BACKEND` 选择实现

2. **向量存储抽象增强**
   - 已有 `BaseVectorStore` + `MilvusVectorStore`
   - 新增 `app/retrieval/pgvector_store.py`
   - 实现 `create_collection` / `insert` / `search` / `delete_by_doc_id`
   - 权限过滤在 SQL `WHERE` 中完成

3. **配置增加开关**
   ```python
   VECTOR_STORE_BACKEND: Literal["milvus", "pgvector"] = "milvus"
   STORAGE_BACKEND: Literal["local", "s3"] = "s3"
   CELERY_BROKER_BACKEND: Literal["redis", "rabbitmq"] = "rabbitmq"
   ```

### Phase 2：Celery 与 Worker 模式（0.5–1 天）

1. `celery_app.py` 根据 `CELERY_BROKER_BACKEND` 选择 broker URL
2. 轻量模式下，文档处理改为同步调用（backend 直接调用 ingest/embed 函数）
3. 全量模式下保持现有 3 Worker 容器

### Phase 3：新增 Docker Compose 文件（0.5–1 天）

1. `docker-compose.lightweight.yml`
   - 4 容器：frontend、backend、postgres-pgvector、redis
   - backend 使用本地存储 + pgvector + Redis broker + 同步处理
2. 调整 `backend/Dockerfile.lightweight`
   - 不安装 OCR/Office 系统库（文档解析走外部服务或禁用复杂格式）
   - 或安装 OCR 但去掉 Worker 相关依赖
3. 创建 `scripts/init-pgvector.sql` 在 Postgres 启动时启用扩展

### Phase 4：依赖拆分（1–2 天）

1. `backend/requirements.txt`：API 层最小依赖（FastAPI/SQLAlchemy/Redis/pydantic/pgvector）
2. `backend/requirements.ingest.txt`：文档解析依赖（unstructured/spacy/pandas/pillow）
3. `backend/Dockerfile` 使用最小依赖
4. `backend/Dockerfile.ingest` 使用解析依赖

### Phase 5：验证与文档（1 天）

1. 轻量化模式下：
   - 注册/登录
   - 创建知识库
   - 上传 PDF/Word
   - 检索与 Chat
   - API Key 认证
   - 权限边界测试
2. 全量化模式下回归测试
3. 更新 README 和部署文档

---

## 6. 预期收益对比

| 指标 | 当前默认 | 轻量化（Phase 3） | 极限压缩（Phase 4+5） |
|------|---------|----------------|---------------------|
| 容器数 | 14 | **5** | **4** |
| 镜像下载 | ~10 GB | **~2.8 GB** | **~1.5 GB** |
| 运行时内存 | 10–16 GiB | **4–5 GiB** | **2 GiB** |
| 建议 CPU | 16 核 | **4 核** | **2 核** |
| 启动时间 | 3–5 min | **< 90 秒** | **< 1 min** |
| 权限 RAG 核心功能 | ✅ 全部 | ✅ 全部 | ⚠️ 可能裁剪复杂解析 |

---

## 7. 风险与 trade-off

| 方案 | 优点 | 缺点 |
|------|------|------|
| **pgvector 替代 Milvus** | 镜像小、易维护、与权限 SQL 天然结合 | 百万级向量后性能下降，需要 IVF/HNSW 调优 |
| **本地文件替代 MinIO** | 零额外服务 | 无 S3 兼容、难做分布式存储 |
| **Redis 替代 RabbitMQ** | 省 392 MB 镜像 | 消息持久化/可靠性弱于 RabbitMQ |
| **后端同步处理** | 省 3 Worker 容器 | 大文件上传会阻塞 API 请求 |
| **去掉 embedding/llm-service** | 省 450 MB | 必须依赖外部 API 或本地模型 |

**建议**：
- 轻量化模式默认用 **pgvector + 本地存储 + Redis broker + 后端同步处理**
- 超过 10 万文档或需要高并发时，切到 **全量化模式**
- 中间态可保留 **pgvector + Redis broker + 独立 Worker**，仍然比 Milvus+RabbitMQ 轻很多

---

## 8. 部署命令建议

### 8.1 轻量化启动

```bash
# 下载并启动 5 容器（frontend/backend/worker/postgres/redis）
docker compose -f docker-compose.lightweight.yml up -d

# 默认账号
# admin / Admin123!
```

### 8.2 全量化启动

```bash
# 默认 14 容器
docker compose up -d

# 加监控 17 容器
docker compose --profile monitoring up -d
```

### 8.3 混合启动（推荐中型生产）

```bash
# pgvector + Redis broker + 独立 Worker（无 Milvus/MinIO/RabbitMQ/Kong）
docker compose -f docker-compose.pgvector.yml up -d
```

---

## 9. 下一步建议

如果你认可这个方案，建议按以下顺序推进：

1. **先实现 Phase 1**（存储抽象 + pgvector）：改动最小、收益最大（减 2 GB+ 镜像）
2. **再做 Phase 2**（Redis broker + 同步处理）：减 3 个 Worker 容器
3. **最后做 Phase 4**（依赖拆分）：把后端镜像压到 700 MB 以下

整个改造完成后，项目将同时具备：
- **开发/POC**：`docker-compose.lightweight.yml`（4 容器、3–4 GiB 内存）
- **企业生产**：`docker-compose.yml`（完整架构、横向扩展）
- **中型过渡**：可单独使用 pgvector + Redis broker 的混合模式

是否需要我直接开始实现 Phase 1（pgvector + 本地存储抽象）？
