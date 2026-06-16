# 后端数据库与中间件连通性测试报告

**测试时间：** 2026-06-16T03:10:51Z  
**测试环境：** Windows 11 + Docker Desktop（Git Bash）  
**项目根目录：** `C:/Users/wuton/Desktop/企业级私有rag`  
**目标容器：** `rag-app-backend`（service: app-backend）

---

## 1. 容器运行状态

```text
NAME                         SERVICE               STATUS
rag-app-backend              app-backend           Up About an hour (healthy)
rag-postgres                 postgres              Up About an hour (healthy)
rag-redis                    redis                 Up About an hour (healthy)
rag-rabbitmq                 rabbitmq              Up About an hour (healthy)
rag-milvus                   milvus-standalone     Up About an hour (healthy)
rag-minio                    minio                 Up About an hour (healthy)
rag-etcd                     etcd                  Up About an hour (healthy)
```

所有基础设施容器均处于 `healthy` 状态。

---

## 2. 后端容器内环境变量 / 连接字符串

| 组件 | 环境变量 | 容器内实际值 |
|------|----------|--------------|
| PostgreSQL | `DATABASE_URL` | `postgresql://rag_user:rag_password@postgres:5432/rag_kb` |
| Redis | `REDIS_URL` | `redis://redis:6379/0` |
| RabbitMQ | `RABBITMQ_URL` | `amqp://guest:guest@rabbitmq:5672/` |
| Milvus | `MILVUS_HOST` / `MILVUS_PORT` | `milvus-standalone` / `19530` |
| MinIO | `MINIO_ENDPOINT` | `minio:9000` |
| MinIO | `MINIO_ACCESS_KEY` | `minioadmin` |
| MinIO | `MINIO_BUCKET` | `rag-documents` |

与 `docker-compose.yml` 中的默认值及挂载的 `backend/.env` 一致，连接字符串配置正确。

---

## 3. 连通性测试结果

### 3.1 PostgreSQL

- **测试命令：** 容器内 Python，使用 `asyncpg` 连接 `postgres:5432` 执行 `SELECT 1`
- **结果：** ✅ 可达
- **输出：**
  ```text
  URL=postgresql://rag_user:rag_password@postgres:5432/rag_kb
  Postgres asyncpg OK: {'one': 1}
  ```
- **说明：** 后端代码 `app/database.py` 使用 `create_async_engine` + `postgresql+asyncpg://`，因此 `DATABASE_URL` 会被自动替换为 asyncpg URL，实际运行正常。

> ⚠️ **发现问题：** 容器内未安装 `psycopg2`、`psycopg` 或 `pg8000`。若使用同步 `postgresql://` URL（如 `create_engine(url)`）直接连接，会报 `ModuleNotFoundError: No module named 'psycopg2'`。

### 3.2 Redis

- **测试命令：** 容器内 Python，使用 `redis-py` 8.0.0 通过 `REDIS_URL` 连接并 `PING`
- **结果：** ✅ 可达
- **输出：**
  ```text
  REDIS_URL=redis://redis:6379/0
  Redis ping: True
  Redis info server: 7.4.9
  ```

> ⚠️ **发现问题：** 容器内没有 `redis-cli` 命令行工具，无法直接执行 `redis-cli -h redis ping`。

### 3.3 Milvus

- **测试命令：** 容器内 Python，使用 `pymilvus` 3.0.0 连接 `milvus-standalone:19530`
- **结果：** ✅ 可达
- **输出：**
  ```text
  Milvus host=milvus-standalone, port=19530
  Milvus connect OK
  Milvus server version: v2.4.1
  ```
- **提示：** `pymilvus 3.0.0` 的 ORM-style API（`connections.connect`）已标记为废弃，建议后续迁移到 `MilvusClient`。

### 3.4 RabbitMQ

- **测试命令：** 容器内 Python，使用 `aio-pika` 9.6.2 连接 `rabbitmq:5672`，创建并删除临时队列
- **结果：** ✅ 可达
- **输出：**
  ```text
  RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
  RabbitMQ channel OK
  RabbitMQ queue declare/delete OK
  ```

> ⚠️ **发现问题：** 容器内未安装 `pika`（同步 RabbitMQ 客户端）。如果测试脚本或部分 worker 依赖 `pika`，会报 `ModuleNotFoundError: No module named 'pika'`。

### 3.5 MinIO

- **测试命令：** 容器内 Python，使用 `boto3` 1.43.30 以 S3-compatible 方式连接 `minio:9000`，列出 buckets 并检查目标 bucket
- **结果：** ✅ 可达
- **输出：**
  ```text
  MINIO_ENDPOINT=minio:9000, bucket=rag-documents
  MinIO list_buckets OK: ['a-bucket', 'rag-documents']
  MinIO bucket rag-documents exists and accessible
  ```

> ⚠️ **发现问题：** 容器内未安装 `minio` Python SDK。若代码直接 `import minio`，会失败；当前项目使用 `boto3` 访问 MinIO，可正常工作。

---

## 4. 后端综合健康检查

```bash
curl -sS http://localhost:8080/api/v1/health
```

**返回结果：**

```json
{
  "status": "ok",
  "services": {
    "postgres": { "status": "ok", "latency_ms": 2.17 },
    "redis":    { "status": "ok", "latency_ms": 4.71 },
    "rabbitmq": { "status": "ok", "latency_ms": 13.77 },
    "milvus":   { "status": "ok", "latency_ms": 210.02 },
    "minio":    { "status": "ok", "latency_ms": 13.41 }
  }
}
```

后端应用本身能正常连接所有依赖的中间件。

---

## 5. Alembic 版本检查

```bash
alembic current
alembic heads
```

- **当前版本：** `20260615_add_field_permission_config (head)`
- **heads：** 仅一个 head `20260615_add_field_permission_config`
- **结论：** ✅ Alembic 已处于最新版本，无需升级。

---

## 6. 发现的问题汇总

| 序号 | 问题 | 影响 | 建议修复 |
|------|------|------|----------|
| 1 | 容器内缺少 `psycopg2` / `psycopg` / `pg8000` | 无法使用同步 SQLAlchemy `create_engine(DATABASE_URL)` 直接连接 PostgreSQL；但后端使用 asyncpg，实际不影响运行 | 若希望兼容同步连接测试或外部脚本，在 `backend/requirements.txt` 添加 `psycopg[binary]>=3.0` 或 `psycopg2-binary` |
| 2 | 容器内缺少 `redis-cli` | 无法直接执行 `redis-cli` 命令行调试 | 在 `backend/Dockerfile` 中安装 `redis-tools`（Debian）或改用 Python `redis-py` 进行测试 |
| 3 | 容器内缺少 `pika` | 依赖同步 RabbitMQ 客户端的脚本会失败；后端使用 `aio-pika`/`celery`，运行正常 | 如确需同步客户端，在 `requirements.txt` 添加 `pika>=1.3` |
| 4 | 容器内缺少 `minio` Python SDK | 直接 `import minio` 会失败；当前使用 `boto3` 访问 S3 API，运行正常 | 若希望使用 MinIO 原生 SDK，添加 `minio>=7.2` |
| 5 | `pymilvus` 3.0.0 ORM-style API 已弃用 | 未来版本（3.1+）将移除，产生告警 | 逐步迁移到 `from pymilvus import MilvusClient` |

---

## 7. 总体结论

- **网络连通性：** 全部通过（Postgres、Redis、Milvus、RabbitMQ、MinIO 均可在后端容器内解析 DNS 并正常通信）。
- **认证 / 权限：** 全部通过，无认证失败或 bucket 不存在问题。
- **后端应用健康：** 通过 `/api/v1/health`，所有依赖服务返回 `ok`。
- **数据库迁移：** Alembic 处于最新 head，无待执行迁移。
- **主要风险：** 容器镜像缺少部分同步客户端（psycopg2、pika、minio SDK、redis-cli），若测试规范或外部脚本强制依赖这些工具，会出现 `ModuleNotFoundError` 或命令找不到。建议根据实际使用场景补充安装，或统一使用已安装的异步/兼容库（`asyncpg`、`aio-pika`、`boto3`、`redis-py`）。
