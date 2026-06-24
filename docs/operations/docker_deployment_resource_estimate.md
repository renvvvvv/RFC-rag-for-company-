# 企业级私有 RAG — Docker 容器化部署资源估算

> 估算基准：当前优化后的镜像（Commit `d34e5a2`）
> 环境参考：Windows + Docker Desktop (WSL2)，16 核 / 12.6 GiB 内存
> 估算日期：2026-06-24

---

## 1. 核心结论

| 部署模式 | 镜像下载 | 运行时内存（建议预留） | 运行时 CPU | 说明 |
|---------|---------|----------------------|-----------|------|
| **最小开发栈**（无 Worker、无监控） | ~6 GB | 3–4 GiB | 4 核 | 仅后端 + 前端 + 数据库 |
| **标准单机构建**（默认 `docker compose up -d`） | **~10 GB** | **8–10 GiB** | **8 核** | 当前默认 14 容器 |
| **标准 + 监控**（加 `--profile monitoring`） | **~11 GB** | **9–11 GiB** | **8 核** | 多 Prometheus/Grafana/Alertmanager |
| **生产预留**（数据增长、并发、副本） | 同左 | **16 GiB+** | **16 核+** | 建议按 2 倍容量规划 |

> ⚠️ 注意：上面的“运行时内存”是按 `deploy.resources.limits` 上限求和得出的**安全值**，不是当前实测值。当前空载实测约 5.5 GiB，但上线后因 Milvus 索引、Worker 积压、文档解析会逼近上限。

---

## 2. 镜像占用明细

### 2.1 应用层镜像

| 镜像 | 大小 | 说明 |
|------|------|------|
| `your-dockerhub-username/rag-backend` | **1.63 GB** | FastAPI 主服务 |
| `rag-system-migrate` | **1.63 GB** | Alembic 一次性迁移，可与后端共享镜像 |
| `rag-system-ingest-worker` | **2.34 GB** | 文档解析（含 OCR/Office 依赖） |
| `rag-system-embed-worker` | **1.61 GB** | 向量化 Worker |
| `rag-system-permission-sync-worker` | **1.61 GB** | 权限同步 Worker |
| `rag-system-embedding-service` | 225 MB | 外部 Embedding 服务（当前为 mock） |
| `rag-system-llm-service` | 225 MB | 外部 LLM 服务（当前为 mock） |
| `your-dockerhub-username/rag-frontend` | 94 MB | React + nginx |
| `kong:3.5` | 414 MB | API 网关 |
| **应用层小计** | **~8.8 GB** | |

### 2.2 数据层镜像

| 镜像 | 大小 | 说明 |
|------|------|------|
| `postgres:16` | 642 MB | 关系型数据库 |
| `redis:7-alpine` | 58 MB | 缓存 / 限流 |
| `rabbitmq:3-management` | 392 MB | 消息队列 |
| `milvusdb/milvus:v2.4.1` | **2.28 GB** | 向量数据库（standalone） |
| `gcr.io/etcd-development/etcd:v3.5.5` | 273 MB | Milvus 元数据 |
| `minio/minio` | 220 MB | 对象存储 |
| **数据层小计** | **~3.9 GB** | |

### 2.3 可观测性镜像（可选）

| 镜像 | 大小 | 说明 |
|------|------|------|
| `prom/prometheus:v2.53.0` | 380 MB | 指标采集 |
| `grafana/grafana:10.4.4` | 577 MB | 可视化 |
| `prom/alertmanager:v0.27.0` | 106 MB | 告警 |
| **监控层小计** | **~1.1 GB** | |

### 2.4 下载总量

- **默认栈**：应用层 8.8 GB + 数据层 3.9 GB = **12.7 GB 本地总占用**
- 考虑到镜像层共享（backend/migrate 共享大部分层），实际网络下载约 **10 GB**
- 加监控后实际下载约 **11 GB**

---

## 3. 运行时资源估算

### 3.1 默认栈（14 容器，无监控）

| 服务 | CPU 限制 | 内存限制 | 实测内存（空载） | 备注 |
|------|---------|---------|-----------------|------|
| Kong | 1.0 | 1.5 GiB | ~1.0 GiB | 内存大户，已被限制 |
| app-backend | 1.0 | 1 GiB | ~460 MiB | |
| ingest-worker | 1.0 | 1.5 GiB | ~1.15 GiB | 文档解析时可能满 |
| embed-worker | 1.0 | 1.5 GiB | ~1.15 GiB | 向量化时 CPU 高 |
| permission-sync-worker | 0.5 | 1.5 GiB | ~1.15 GiB | |
| embedding-service | 0.5 | 256 MiB | ~34 MiB | mock 服务 |
| llm-service | 0.5 | 256 MiB | ~34 MiB | mock 服务 |
| frontend | 0.25 | 128 MiB | ~13 MiB | |
| postgres | 0.5 | 1 GiB | ~30 MiB | 随数据量增长 |
| redis | 0.25 | 256 MiB | ~7 MiB | |
| rabbitmq | 0.5 | 512 MiB | ~195 MiB | |
| milvus-standalone | 2.0 | 2 GiB | ~68 MiB | 索引/检索时 CPU 满载 |
| etcd | 0.5 | 512 MiB | ~187 MiB | |
| minio | 0.5 | 512 MiB | ~272 MiB | |
| **合计** | **~9.5 核** | **~11.9 GiB** | **~5.5 GiB** | |

> **建议服务器内存**：按 limits 总和预留 **12 GiB**，留 20% 余量即 **16 GiB**。
> **建议服务器 CPU**：10 核以上物理核（或 16 逻辑核）。

### 3.2 标准栈 + 监控（17 容器）

| 服务 | CPU 限制 | 内存限制 |
|------|---------|---------|
| Prometheus | 0.5 | 512 MiB |
| Grafana | 0.5 | 512 MiB |
| Alertmanager | 0.25 | 256 MiB |
| 其他 | 同 3.1 | 同 3.1 |
| **合计** | **~10.75 核** | **~13.2 GiB** |

> **建议服务器内存**：**16 GiB**。
> **建议服务器 CPU**：12 核以上物理核（或 20 逻辑核）。

### 3.3 仅最小开发栈（后端 + 前端 + DB + Redis）

| 服务 | CPU 限制 | 内存限制 |
|------|---------|---------|
| Kong | 1.0 | 1.5 GiB |
| app-backend | 1.0 | 1 GiB |
| frontend | 0.25 | 128 MiB |
| postgres | 0.5 | 1 GiB |
| redis | 0.25 | 256 MiB |
| **合计** | **~3 核** | **~3.9 GiB** |

> 适合本地开发或功能演示，没有文档解析和向量检索能力。

---

## 4. 数据卷增长估算

当前本地卷大小（空载/小数据）：

| 卷 | 当前大小 | 增长因素 | 估算年增量 |
|---|---------|---------|-----------|
| `postgres_data` | ~68 MB | 用户、KB、文档元数据、审计日志 | 1–10 GB/年 |
| `milvus_data` | ~60 MB | 向量索引、原始向量 | 10–100 GB/年（视文档量） |
| `minio_data` | ~0.6 MB | 原始文件（PDF/Word/图片） | 10–500 GB/年 |
| `etcd_data` | ~424 MB | Milvus 元数据 | 1–5 GB/年 |
| `redis_data` | ~0.1 MB | 缓存、限流计数 | <1 GB/年 |
| `rabbitmq_data` | ~0.8 MB | 消息持久化 | <1 GB/年 |
| `prometheus_data` | ~91 MB | 指标时序数据 | 10–50 GB/年 |
| `grafana_data` | ~52 MB | Dashboard、告警配置 | <1 GB/年 |

**存储规划建议**：
- 系统盘：50 GB（镜像 + 容器层 + 日志）
- 数据盘：
  - 小规模（<10 万文档）：100 GB
  - 中规模（10–100 万文档）：500 GB
  - 大规模（>100 万文档）：1 TB+，MinIO/Milvus 考虑独立存储或对象存储服务

---

## 5. 按场景的服务器配置建议

### 5.1 开发/POC（1 台）

```
CPU：8 核
内存：16 GiB
磁盘：200 GB SSD
网络：内网即可
```
- 运行默认栈 + 监控
- 适合 1–5 人团队、<1 万文档

### 5.2 小型生产（1 台）

```
CPU：16 核
内存：32 GiB
磁盘：500 GB SSD
网络：千兆
```
- 运行默认栈 + 监控
- 适合 10–50 人、<10 万文档
- 建议每日备份 PostgreSQL + MinIO

### 5.3 中型生产（2–3 台）

```
应用节点（1 台）：16 核 / 32 GiB / 200 GB
数据节点（1 台）：16 核 / 32 GiB / 500 GB SSD + 1 TB 数据盘
可选监控节点（1 台）：4 核 / 8 GiB / 100 GB
```
- 应用节点跑 Kong/backend/frontend/workers
- 数据节点跑 PostgreSQL/Redis/RabbitMQ/Milvus/etcd/MinIO
- 使用 `docker-compose.app.yml` + `docker-compose.infra.yml` 分体部署
- 适合 50–200 人、<50 万文档

### 5.4 大型生产（K8s / 多节点）

```
Kong：2+ 副本
Backend：3+ 副本
Worker：按队列独立扩缩容（ingest/embed/permission 分开）
PostgreSQL：托管 RDS / 主从
Milvus：Cluster 模式（proxy/query/index/data/etcd/minio 分离）
MinIO：分布式集群
Redis：哨兵或集群
```
- 需要 Helm / Kustomize 编排
- 适合 200+ 人、百万级文档

---

## 6. 关键风险点

1. **Milvus standalone 单核瓶颈**：当前默认部署把 proxy/query/index/data 全放一个容器，CPU 容易打满。超过 10 万文档后强烈建议切换到 Milvus cluster 模式。
2. **Worker 内存占用高**：3 个 Worker 各 1.5 GiB，合计 4.5 GiB。主要因为 Python 依赖未按队列拆分，后续可再优化。
3. **Kong 内存仍偏大**：1 GB+ 常驻，且随连接数增长。生产环境中若流量大，建议独立网关节点或调优 OpenResty。
4. **数据卷未设置上限**：PostgreSQL/Milvus/MinIO 的数据卷会持续增长，需配置日志轮转、向量过期策略、对象生命周期规则。

---

## 7. 快速估算公式

如果你要告诉运维一台服务器能不能跑：

```
最小内存 = 后端 1G + Kong 1.5G + Worker数量 × 1.5G + Milvus 2G + 数据库 1G + 缓存队列 1G + 20% 余量

示例（默认 3 Worker）：
= 1 + 1.5 + 3×1.5 + 2 + 1 + 1 = 10.5 GiB
+ 20% 余量 ≈ 13 GiB
```

```
最小 CPU = 后端 1 + Kong 1 + Worker数量 × 1 + Milvus 2 + 数据库/缓存 1 = 7–8 核
建议物理核 ≥ 10
```

---

## 8. 结论

以当前优化后的版本：**单台 16 核 / 16–32 GiB 内存 / 500 GB SSD 的服务器** 可以稳定运行整套系统（含监控）。如果只做开发验证，**8 核 / 16 GiB 内存** 也足够。

如果目标是企业级生产部署，建议按 **32 GiB 内存 + 独立数据盘 + 16 核 CPU** 起步，并根据文档量和并发量横向扩展 Worker 与 Milvus。
