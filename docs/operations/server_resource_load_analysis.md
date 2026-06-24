# 企业级私有 RAG 服务器资源负载分析

> 分析时间：2026-06-24  
> 分析对象：`docker-compose.yml` + `k8s/helm/rag-system/values.yaml` + 当前本地运行实例  
> 主机配置：16 逻辑核 / 12.6 GiB 内存 / Windows + Docker Desktop

---

## 1. 部署 footprint 总览

当前项目通过 Docker Compose 全栈启动时，会拉起 **17 个容器**，涵盖：

| 层级 | 组件 |
|---|---|
| 网关 | Kong |
| 应用 | FastAPI Backend、React Frontend |
| 异步 Worker | ingest-worker、embed-worker、permission-sync-worker |
| 模型服务 | embedding-service、llm-service |
| 数据存储 | PostgreSQL、Redis、RabbitMQ、MinIO、Milvus、etcd |
| 可观测 | Prometheus、Grafana、Alertmanager |

**现状风险**：
- Docker Compose 中 **没有任何容器配置 `deploy.resources` 限制**，所有服务共享宿主机资源，容易出现“噪声邻居”。
- Helm 默认 values 虽有 requests/limits，但偏保守（如 backend limit 4Gi/2核），且未按生产并发校准。

---

## 2. 当前本地实例实际资源占用

基于 `docker stats --no-stream`（2026-06-24 实测）：

| 容器 | CPU | 内存 | 备注 |
|---|---|---|---|
| rag-milvus | **107.98%** | 164.3 MiB | 正在执行索引/compact，CPU 热点 |
| rag-rabbitmq | 37.06% | 224.5 MiB | embed 队列积压时负载升高 |
| rag-minio | 34.60% | 299.5 MiB | IO 密集型 |
| rag-embed-worker | 24.62% | 1.176 GiB | 向量化任务瓶颈 |
| rag-etcd | 22.74% | 196.5 MiB | Milvus 元数据存储 |
| rag-ingest-worker | 1.64% | 1.199 GiB | 大镜像加载后常驻内存高 |
| rag-permission-sync-worker | 2.14% | 1006 MiB | 大镜像常驻内存高 |
| rag-app-backend | 1.98% | 497.4 MiB | 2 个 uvicorn worker |
| rag-kong | 1.19% | 1.181 GiB | Kong 3.5 默认内存占用偏高 |
| rag-postgres | 0.00% | 78.6 MiB | 当前负载低 |
| rag-redis | 0.61% | 6.965 MiB | 轻量 |
| rag-grafana | 0.10% | 85.93 MiB | 轻量 |
| rag-prometheus | 1.32% | 67.98 MiB | 数据量小时轻量 |
| rag-frontend | 0.00% | 13.19 MiB | 轻量 |
| rag-embedding-service | 0.21% | 39.06 MiB | 轻量（mock 服务） |
| rag-llm-service | 0.20% | 36.47 MiB | 轻量（mock 服务） |
| rag-alertmanager | 0.13% | 22.13 MiB | 轻量 |

**汇总**：
- 项目容器总计占用内存约 **6.5–7 GiB**，占系统内存 **55% 左右**。
- CPU 主要消耗在 **Milvus（索引）、RabbitMQ（队列调度）、MinIO（IO）、embed-worker（向量化）**。
- 三个 Python Worker 容器各自常驻 **~1 GiB**，合计 **~3.4 GiB**，是内存大户。

---

## 3. 各组件负载与瓶颈分析

### 3.1 API Backend（FastAPI）

**配置**：
- Dockerfile: `uvicorn ... --workers 2`
- Helm requests: 500m CPU / 1Gi 内存；limits: 2 CPU / 4Gi 内存
- HPA: CPU 70% / 内存 80%，副本 2–10

**分析**：
- 2 个 uvicorn worker 在 CPU-bound 检索链路下并发能力有限。一次 hybrid search 需要同步调用 embedding + Milvus + BM25 + rerank，GIL 会让单个 worker 阻塞。
- 当前后端内存 497 MiB，远低于 limit，但如果同时处理多个大上下文 chat 请求，内存会快速上升（上下文压缩、历史消息、BM25 加载）。
- HPA 只监控 backend Pod，但**检索延迟主要受下游 Milvus/embedding 影响**，单纯扩容 backend 对检索 P99 改善有限。

**风险**：中等。检索链路长，backend 容易成为“等待型”瓶颈而非计算瓶颈。

### 3.2 Celery Workers

**配置**：
- Dockerfile.worker 未指定 `-c`，Celery 默认并发数 = CPU 核心数（本机 16）。
- Helm 各队列均为 1 副本，embed worker limit 2 CPU / 4Gi。

**分析**：
- **ingest-worker**：解析 PDF/Office/图片，依赖 LibreOffice + Tesseract，CPU 和内存都重。默认 16 并发在 12.6GiB 机器上极易 OOM。
- **embed-worker**：调用 embedding 服务生成向量。当前 embed 队列积压 20+ 条，说明 embed worker 吞吐不足。
- **permission-sync-worker**：轻量，但同样使用 2.34GB 大镜像，内存浪费明显。
- 三个 worker 共享相同 Dockerfile，镜像包含 LibreOffice/Tesseract/PyTorch 等，**单镜像 2.34GB**，启动慢、内存基线高。

**风险**：高。embed 队列是当前明显瓶颈；ingest worker 并发过高有 OOM 风险。

### 3.3 Milvus（向量数据库）

**配置**：
- standalone 模式（etcd + MinIO + Milvus 三合一进程）
- Helm limit: 2 CPU / 4Gi 内存

**分析**：
- 实测 CPU 使用率高达 107%，处于持续索引或 compaction 状态。
- standalone 模式在数据量增长后会把向量索引、对象存储、元数据集中在同一 Pod，**无法独立扩展**。
- 当前 memory 仅 164 MiB 是因为数据量小；一旦文档数上万，4Gi limit 会很快触顶。

**风险**：高。当前是单机 standalone，生产应使用 Milvus cluster 或托管服务。

### 3.4 RabbitMQ

**配置**：
- 单节点，management 插件启用
- 队列：ingest、embed、permission_sync、celery

**分析**：
- embed 队列积压说明 **生产者（ingest）速度 > 消费者（embed）速度**。
- RabbitMQ 在队列积压时 CPU 和内存都会上升，且 ack 超时（实测 1800000 ms）会影响消费稳定性。

**风险**：中等。需要增加 embed worker 并发或实例数，并调整 consumer timeout。

### 3.5 PostgreSQL / Redis / MinIO / etcd

| 组件 | 当前状态 | 风险 |
|---|---|---|
| PostgreSQL | 负载低，78 MiB | 低；但无连接池上限配置，高并发时可能连接数暴涨 |
| Redis | 极轻量，7 MiB | 低；但 AOF everysec 在写入高峰有 IO 开销 |
| MinIO | CPU 34.6%，300 MiB | 中；所有文档原始文件和 Milvus 数据都走 MinIO，IO 和带宽会成瓶颈 |
| etcd | CPU 22.7%，196 MiB | 中；Milvus 元数据，standalone 模式下与 Milvus 同生共死 |

---

## 4. Docker Compose vs Helm 资源配置对比

| 组件 | Docker Compose | Helm values | 评价 |
|---|---|---|---|
| backend | 无限制 | req 0.5/1Gi, lim 2/4Gi, HPA 2–10 | Compose 缺少限制；Helm 相对合理但需按并发校准 |
| frontend | 无限制 | req 0.1/128Mi, lim 0.5/512Mi | 合理 |
| ingest worker | 无限制 | req 0.25/512Mi, lim 1/2Gi | 对解析大文件可能不足 |
| embed worker | 无限制 | req 0.5/1Gi, lim 2/4Gi | 单副本无法处理当前积压 |
| permission-sync worker | 无限制 | req 0.1/256Mi, lim 0.5/1Gi | 合理 |
| postgres | 无限制 | req 0.25/512Mi, lim 1/2Gi, 20Gi PVC | 开发够用，生产建议外部 RDS |
| redis | 无限制 | req 0.1/128Mi, lim 0.5/512Mi, 5Gi PVC | 合理 |
| rabbitmq | 无限制 | req 0.25/512Mi, lim 1/2Gi, 5Gi PVC | 合理 |
| milvus | 无限制 | req 0.5/1Gi, lim 2/4Gi, 20Gi PVC | standalone 模式容量上限明显 |
| minio | 无限制 | req 0.25/512Mi, lim 1/2Gi, 20Gi PVC | 生产建议外部 S3 |
| kong | 无限制 | req 0.25/512Mi, lim 1/1Gi | 合理 |

**关键差距**：
- Docker Compose 完全没有资源隔离，不适合作为任何共享环境的部署方式。
- Helm 缺少 **worker 的 HPA**，只有 backend 能自动扩缩容。

---

## 5. 已暴露的运行时问题

1. **embed worker 队列积压**：RabbitMQ `embed` 队列 20+ 条未消费，文档长期处于 `processing` 状态。
2. **Milvus CPU 打满**：standalone 模式索引/compact 占用大量 CPU。
3. **RabbitMQ consumer ack 超时 1800000 ms**：可能导致消息重复投递或消费停滞。
4. **Worker 镜像过大**：2.34GB，包含 LibreOffice/Tesseract/PyTorch，启动慢、内存基线高。
5. **Backend 2 个 uvicorn worker**：对混合检索这种 IO/CPU 混合型负载，并发处理能力偏低。

---

## 6. 优化建议

### 6.1 立即执行（开发/POC 环境）

1. **为 Docker Compose 增加 `deploy.resources` 限制**，防止单个容器拖垮宿主机：
   ```yaml
   app-backend:
     deploy:
       resources:
         limits:
           cpus: '2.0'
           memory: 2G
         reservations:
           cpus: '0.5'
           memory: 512M
   ```

2. **限制 Celery worker 并发数**，避免 ingest worker 在 16 核机器上启动 16 个解析进程导致 OOM：
   ```dockerfile
   CMD celery -A app.workers.celery_app worker -Q ${WORKER_QUEUE} -c 2 -l info
   ```

3. **增加 embed worker 实例或并发**：当前 embed 是瓶颈，可临时多启动一个 embed-worker 容器。

4. **减小 Worker 镜像**：将 ingest/embed/permission-sync 拆分为不同 Dockerfile，ingest 保留 LibreOffice/Tesseract，embed 只保留向量化依赖，permission-sync 最小化。

### 6.2 短期（测试/预发布环境）

1. **为 Helm worker 增加 HPA**：
   - ingest worker：基于 RabbitMQ 队列长度或 CPU
   - embed worker：基于队列长度或 GPU 利用率（如有 GPU）

2. **Backend 并发调优**：
   - 若仍以 CPU-bound 同步调用为主，可试用 `gunicorn` + `uvicorn.workers.UvicornWorker` 并增加 worker 数。
   - 更优方案是将 embedding/Milvus/BM25/rerank 全部改为真正的异步或线程池，释放 GIL。

3. **Milvus 容量规划**：
   - 文档 < 10 万：standalone + 4Gi 内存可支撑。
   - 文档 > 10 万或并发 > 50 QPS：必须切换到 Milvus cluster 或使用托管向量库。

### 6.3 长期（生产环境）

1. **按 `values-production.yaml` 禁用内置有状态服务**，使用外部托管服务：
   - RDS / Cloud SQL 替代自建 PostgreSQL
   - ElastiCache / MemoryDB 替代自建 Redis
   - CloudAMQP / Amazon MQ 替代自建 RabbitMQ
   - S3 / OSS 替代自建 MinIO
   - Milvus cluster 或 Zilliz Cloud 替代 standalone

2. **监控告警完善**：
   - 默认 Prometheus 未启用 `node-exporter`、`postgres-exporter` 等，建议 `--profile monitoring-exporters` 启动。
   - 增加 embed queue length 告警阈值（当前 100）。

3. **容量基准测试**：
   - 使用 Locust/k6 压测 `/api/v1/search` 和 `/api/v1/external/chat`，找到 backend/Milvus/worker 的饱和点。
   - 根据 P99 延迟和错误率重新校准 HPA 阈值与资源 limits。

---

## 7. 生产环境最小资源建议

基于当前 17 容器 footprint 和 Helm values，以下为一个中小型部署（100 并发、10 万文档）的参考 sizing：

| 组件 | 副本 | CPU Request | CPU Limit | 内存 Request | 内存 Limit | 存储 |
|---|---|---|---|---|---|---|
| Kong | 2 | 250m | 1000m | 512Mi | 1Gi | - |
| Backend | 3–5 (HPA) | 500m | 2000m | 1Gi | 4Gi | - |
| Frontend | 2 | 100m | 500m | 128Mi | 512Mi | - |
| Ingest Worker | 2–4 (HPA) | 500m | 2000m | 1Gi | 4Gi | - |
| Embed Worker | 2–4 (HPA) | 1000m | 4000m | 2Gi | 8Gi | - |
| Permission Sync Worker | 1–2 | 100m | 500m | 256Mi | 1Gi | - |
| PostgreSQL | 外部 RDS | - | - | - | - | 100Gi+ |
| Redis | 外部缓存 | - | - | - | - | - |
| RabbitMQ | 外部队列 | - | - | - | - | - |
| MinIO / S3 | 外部对象存储 | - | - | - | - | 500Gi+ |
| Milvus | Cluster 或托管 | - | - | - | - | 500Gi+ |
| Prometheus | 1 | 250m | 1000m | 512Mi | 2Gi | 100Gi |
| Grafana | 1 | 100m | 500m | 256Mi | 1Gi | 5Gi |

**总节点建议**：3 台 8 核 32GiB 节点（用于应用 + 监控），有状态服务全部外置。

---

## 8. 结论

- 当前本地全栈部署对一台 16 核 / 12.6 GiB 的机器来说**已经比较吃力**，内存占用 ~55%，CPU 在 Milvus 索引时接近满载。
- **最大瓶颈目前是 embed worker（队列积压）和 Milvus standalone（CPU/扩展性）**。
- Docker Compose 仅适合开发，**生产必须使用 Helm + 外部有状态服务**。
- 建议优先执行：拆分 worker 镜像、限制 worker 并发、为 Docker Compose 增加资源限制、为 Helm worker 增加 HPA。
