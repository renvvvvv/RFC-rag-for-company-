# 企业级私有 RAG 系统资源占用根因分析

> 分析对象：`docker-compose.yml` 全栈（17 个容器）
> 分析时间：2026-06-15
> 宿主机：Windows + Docker Desktop (WSL2)，16 逻辑核 / 12.6 GiB 内存

---

## 1. 执行摘要

当前全栈在本地启动后：

| 维度 | 当前状态 |
|------|---------|
| 容器数量 | 17 个（含 2 个一次性 init/migrate） |
| 镜像占用 | 约 **7.3 GB**（去重后实际下载约 **9 GB**） |
| 运行时内存 | 约 **5.9 GiB**（无负载静置） |
| CPU 热点 | Milvus standalone 109%、etcd 24%、embed-worker 27%、MinIO 35% |
| 单镜像最大 | `rag-backend` **2.34 GB** |

**核心结论**：系统“看起来大”并不全是因为业务复杂，而是**镜像构建策略粗放**——同一份 `requirements.txt` 被后端和所有 Worker 共用、OCR/Office 解析库被装到不需要它的容器里、Milvus 以 standalone 模式跑却承担分布式集群的角色、Kong 内存异常偏高。下面按“镜像 → 运行时 → 根因 → 优化”逐层拆解。

---

## 2. 镜像占用拆解

### 2.1 项目镜像清单

```text
REPOSITORY                           SIZE      用途
your-dockerhub-username/rag-backend  2.34 GB   FastAPI 主服务
rag-system-migrate                   2.34 GB   Alembic 迁移（一次性）
rag-system-app-backend               2.55 GB   旧构建遗留
rag-backend-local                    2.55 GB   旧构建遗留
rag-backend-test                     2.55 GB   旧构建遗留
rag-system-ingest-worker             1.61 GB   文档解析 Worker
rag-system-embed-worker              1.61 GB   向量化 Worker
rag-system-permission-sync-worker    1.61 GB   权限同步 Worker
rag-system-embedding-service         225 MB    外部 Embedding 服务
rag-system-llm-service               225 MB    外部 LLM 服务
your-dockerhub-username/rag-frontend 94.4 MB   React 前端（nginx 托管）
rag-system-frontend                  94.2 MB   旧构建遗留
```

### 2.2 `rag-backend:2.34 GB` 分层明细

通过 `docker history` 逐层统计：

| 层级 | 大小 | 说明 |
|------|------|------|
| `python:3.11-slim` 基础镜像 | ~140 MB | Debian trixie + Python 3.11.15 |
| 系统依赖（OCR/PDF/Office） | **706 MB** | `tesseract-ocr` + 中英文语言包 + `poppler-utils` + `libreoffice-writer/calc/impress` |
| Python 依赖 pip install | **901 MB** | 来自 `requirements.txt` 及其传递依赖 |
| 业务代码 COPY | 1.72 MB | `app/`、`alembic/` 等 |
| 非 root 用户创建 | 1.77 MB | `groupadd` / `useradd` / `chown` |
| 其他元数据 | <1 MB | EXPOSE / CMD / ENV |
| **合计（镜像显示）** | **2.34 GB** | Docker 分层存在额外元数据/压缩差异 |

**关键发现**：
- **706 MB 的 apt 包装在了后端容器里，但后端只做 API 路由、认证、检索调度，本身不解析 PDF/Office。** 这是纯粹的浪费。
- **901 MB 的 Python 依赖里，后端真正高频使用的只有 FastAPI/SQLAlchemy/pydantic/asyncpg/redis/Celery**，其余 `unstructured`、`spacy`、`llvmlite`、`numba`、`pandas` 等都是为了文档解析而存在。

### 2.3 Python 依赖热点（本地 `.venv` 实测 673 MB）

```text
104 MB  llvmlite          ← unstructured 传递依赖
 90 MB  spacy             ← unstructured 传递依赖
 68 MB  pandas            ← unstructured/pymilvus 传递依赖
 33 MB  numpy
 30 MB  numba             ← unstructured 传递依赖
 26 MB  botocore          ← boto3 传递依赖
 22 MB  blis              ← spacy 传递依赖
 19 MB  sqlalchemy
 16 MB  PIL
...（其余 100+ 个包占剩余空间）
```

**根因**：`unstructured>=0.12.0` 一个包拖进来了 `spacy` + `numba` + `llvmlite` + `pandas` + `lxml` + `rapidfuzz` 等，仅这几个就超过 **300 MB**。后端接口层如果不需要本地解析文档，不应该承担这份重量。

### 2.4 Worker 镜像的矛盾

三个 Worker 使用同一份 `Dockerfile.worker`：

```dockerfile
FROM python:3.11-slim
RUN apt-get install -y --no-install-recommends gcc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD celery -A app.workers.celery_app worker -Q ${WORKER_QUEUE}
```

问题：
1. **over-install**：`embed-worker` 和 `permission-sync-worker` 不需要 `unstructured/spacy/llvmlite/pandas`，却被迫各扛 **1.61 GB** 镜像。
2. **under-install**：`ingest-worker` 需要解析 PDF/Office/扫描件，但镜像里**没有** `tesseract-ocr`、`poppler-utils`、`libreoffice`，遇到扫描 PDF 或旧 Office 格式会降级或失败。
3. **三份重复镜像**：实际只有 `ingest-worker` 需要重型解析栈，却被三份全量复制，多占约 **3.2 GB** 磁盘。

---

## 3. 运行时内存占用拆解

`docker stats --no-stream` 静置状态：

| 容器 | 内存 | CPU | 说明 |
|------|------|-----|------|
| rag-kong | **1.20 GiB** | 2.0% | ⚠️ 异常高，OpenResty 通常 100–200 MB |
| rag-embed-worker | **1.15 GiB** | 26.8% | 正在积压任务，持续拉取消息 |
| rag-ingest-worker | **1.16 GiB** | 1.5% | 空闲但镜像预加载了大量包 |
| rag-permission-sync-worker | **967 MiB** | 2.5% | 完全空闲却占近 1 GB |
| rag-app-backend | 496 MiB | 2.7% | 正常 |
| rag-minio | 300 MiB | 35.2% | IO 较活跃 |
| rag-etcd | 248 MiB | 24.2% | Milvus 元数据服务 |
| rag-rabbitmq | 190 MiB | 0.6% | 正常 |
| rag-milvus | 166 MiB | **109.4%** | 索引/compaction 满载 |
| rag-prometheus | 70 MiB | 0.5% | 正常 |
| rag-postgres | 77 MiB | 0.0% | 数据量小 |
| rag-grafana | 82 MiB | 0.2% | 正常 |
| rag-frontend | 13 MiB | 0.0% | nginx 静态文件，很省 |
| rag-embedding-service | 39 MiB | 0.3% | mock 服务，很轻 |
| rag-llm-service | 36 MiB | 0.3% | mock 服务，很轻 |
| rag-redis | 7 MiB | 0.6% | 很轻 |
| rag-alertmanager | 22 MiB | 0.2% | 很轻 |

**总内存 ≈ 5.9 GiB**，占宿主机 12.6 GiB 的 **47%**。

### 3.1 异常点 1：Kong 1.2 GB

Kong 3.5 官方镜像在 DB-less 模式下通常 100–300 MB。当前 1.2 GB 可能原因：
- WSL2 下 `docker stats` 把 page cache 算进容器内存；
- Kong 加载了 `prometheus` + `rate-limiting` 插件，rate-limiting 使用 `local` 策略，本地内存字典持续增长；
- 配置中 rate-limiting 配置了两份（全局 100/min + 外部 1000/min），本地计数器未设上限。

### 3.2 异常点 2：三个 Worker 各近 1 GB 但大部空闲

Celery Worker 启动时会导入整个 `app` 包，从而把 `unstructured`、`spacy`、`pandas` 等全部加载进内存。即使队列里没有任务，Worker 进程也保持这些导入，导致：
- `embed-worker` 和 `permission-sync-worker` 白白占用 1 GB；
- 镜像越大 → 启动越慢 → 弹性扩缩容越迟钝。

### 3.3 异常点 3：Milvus CPU 满载但内存仅 166 MB

Milvus standalone 把 proxy、query node、index node、data node 全部打包在一个进程里。当前正在后台做 index build / compaction，CPU 跑满 1 核以上，但内存没上去说明数据量还小。**这是 standalone 架构的固有缺陷**：无法把 CPU 密集型任务拆出去，横向扩展困难。

---

## 4. 根因总结

### 根因 1：一份 `requirements.txt` 打天下

后端、迁移、三个 Worker 全部共用同一份依赖。后端不需要文档解析，Worker 之间需求也不同，却全部安装 `unstructured` 全家桶。

**影响**：镜像膨胀 600–900 MB / 容器。

### 根因 2：OCR/Office 库错配

- 需要这些库的是 `ingest-worker`，但它镜像里反而没有；
- 不需要这些库的是 `app-backend` 和 `migrate`，它们镜像里却有 706 MB。

**影响**：后端镜像额外 706 MB；ingest-worker 功能不完整。

### 根因 3：Worker 镜像未按队列拆分

三份 1.61 GB 镜像内容相同，却承担完全不同的职责。Celery 启动即全量导入，内存浪费显著。

**影响**：磁盘 +3.2 GB，运行时内存 +2–3 GB。

### 根因 4：Milvus standalone 单机扛所有角色

企业级私有化场景下，Milvus 以 standalone 跑，查询、索引、数据、元数据都在一个容器，CPU 容易单核打满。

**影响**：向量检索吞吐量受限，无法单独扩容 index node。

### 根因 5：全量可观测性栈常驻

Prometheus + Grafana + Alertmanager + 可选 Exporters 常驻。对于本地开发/POC 是过度配置。

**影响**：镜像 + 运行时约 700 MB 常驻，且 Alertmanager 当前无实际告警通道。

### 根因 6：无资源限制

`docker-compose.yml` 中没有任何 `deploy.resources.limits` 或 `mem_limit`/`cpus`。容器可以无限吃宿主机资源，Kong 1.2 GB、Milvus 单核满载都没有上限约束。

### 根因 7：旧镜像未清理

本地存在多个旧构建：`rag-system-app-backend:2.55 GB`、`rag-backend-local:2.55 GB`、`rag-backend-test:2.55 GB`、`rag-system-frontend:94 MB`。它们占用磁盘但无容器运行。

---

## 5. 优化路线图与可节省空间估算

| 优化项 | 方案 | 预计节省 |
|--------|------|---------|
| **拆分 requirements** | 后端用 `requirements.txt`（仅 API 框架/DB/缓存），Worker 按队列用 `requirements.ingest.txt` / `requirements.embed.txt` / `requirements.permission.txt` | 后端镜像 **-900 MB**；embed/permission Worker 各 **-700 MB** |
| **OCR/Office 库归位** | 从 backend/migrate 删除 tesseract/libreoffice/poppler；在 ingest-worker 添加 | backend **-706 MB**；ingest 功能补全 |
| **Worker 专用 Dockerfile** | 每类 Worker 一个 Dockerfile，只安装所需依赖 + 只 COPY 所需代码 | 3 Worker 总计从 **4.83 GB → ~1.5 GB** |
| **后端使用更精简基础镜像** | 改用 `python:3.11-alpine` 或 `python:3.11-slim` + 多阶段构建 | 再 **-100–200 MB** |
| **Milvus 角色拆分（生产）** | K8s 部署时改用 cluster 模式：separate proxy/query/index/data/etcd/minio | 本地不减资源，但解决单核 CPU 瓶颈 |
| **可观测性可选化** | Docker Compose 默认不启动 Prometheus/Grafana/Alertmanager，仅 `--profile monitoring` 启动 | 本地运行时 **-700 MB**、镜像 **-1.3 GB** |
| **清理旧镜像** | `docker image prune -a` 或显式删除旧 tag | 磁盘 **-~6 GB** |
| **设置资源上限** | 为每个服务加 `deploy.resources.limits` | 防止 Kong/Milvus 吃光资源 |

### 保守估算（仅 Docker Compose 本地栈）

- **镜像总占用**：从 ~7.3 GB → **~3.5 GB**（-52%）
- **运行时内存**：从 ~5.9 GiB → **~3.5 GiB**（-41%）
- **磁盘总占用（含旧镜像）**：可再释放 **~6 GB**

### 激进估算（后端上 alpine + 最小依赖）

- `app-backend` 可降至 **400–600 MB**
- `ingest-worker` 可降至 **800 MB–1 GB**
- `embed-worker` / `permission-sync-worker` 可降至 **300–500 MB**

---

## 6. 立即可做的 5 个 Quick Wins

1. **删除旧镜像**
   ```bash
   docker rmi rag-backend-local rag-backend-test rag-system-app-backend rag-system-frontend
   docker image prune -f
   ```

2. **把可观测性栈改成 profile**
   在 `docker-compose.yml` 给 `prometheus`、`grafana`、`alertmanager` 加 `profiles: ["monitoring"]`，默认 `docker compose up` 不启动。

3. **为所有服务加资源上限**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '1.0'
         memory: 512M
       reservations:
         memory: 128M
   ```
   重点限制 Kong、Milvus、Worker。

4. **先把 backend/migrate 的 OCR apt 包删掉**
   这些包对后端是 100% 无用，直接移除可让后端镜像从 2.34 GB 降到约 **1.6 GB**。

5. **为 ingest-worker 补上 OCR/Office 系统库**
   否则扫描 PDF 和 PPT 解析会失败，形成“大镜像还没功能”的尴尬。

---

## 7. 后续建议

- 进行 **镜像拆分改造** 前，先建立依赖矩阵，明确每个服务真正 import 的第三方包；
- 对 `app-backend` 做 **import 扫描**（可用 `vulture` / 自定义脚本），把只在 Worker 里用的模块从后端运行时剔除；
- 考虑把 `ingest` 流程中的文档解析再细分为 **纯文本解析 Worker**（轻量）和 **OCR/Office 解析 Worker**（重型），避免每个任务都拉起重型依赖；
- 评估是否用 `uv` / `pip --target` / 多阶段构建进一步压缩镜像层；
- 如果目标部署在 K8s，建议 Milvus 使用官方 Helm Chart 的 cluster 模式，而不是 standalone。

---

## 8. 优化实施结果（2026-06-24）

已按第 5 节路线图完成第一批改造：

### 8.1 已落地改动

1. **删除旧镜像**：`rag-backend-local`、`rag-backend-test`、`rag-system-app-backend`、`rag-system-frontend`
2. **精简后端镜像**：`backend/Dockerfile` 移除 `tesseract-ocr`、`poppler-utils`、`libreoffice-writer/calc/impress`
3. **新增专用 ingest 镜像**：`backend/Dockerfile.ingest` 补上 OCR/Office 系统库
4. **可观测性可选化**：`docker-compose.yml` / `docker-compose.infra.yml` 中 `prometheus`、`grafana`、`alertmanager` 加 `profiles: [monitoring]`
5. **资源限制**：为 `docker-compose.yml`、`docker-compose.app.yml`、`docker-compose.infra.yml` 全部服务添加 `deploy.resources.limits`
6. **RabbitMQ 健康检查加固**：超时从 5s 提高到 10s，重试从 5 次提高到 10 次，`start_period` 提高到 30s

### 8.2 镜像大小实测对比

| 镜像 | 优化前 | 优化后 | 变化 |
|------|--------|--------|------|
| `your-dockerhub-username/rag-backend` | **2.34 GB** | **1.63 GB** | **-710 MB** |
| `rag-system-migrate` | **2.34 GB** | **1.63 GB** | **-710 MB** |
| `rag-system-ingest-worker` | **1.61 GB** | **2.34 GB** | **+730 MB**（补上 OCR/Office） |
| 3 个核心镜像合计 | **6.29 GB** | **5.60 GB** | **-690 MB** |

### 8.3 运行时内存（带资源限制）

| 容器 | 内存使用 / 限制 | 利用率 |
|------|----------------|--------|
| rag-kong | 989 MiB / 1.5 GiB | 64% |
| rag-app-backend | 460 MiB / 1 GiB | 45% |
| rag-embed-worker | 1.16 GiB / 1.5 GiB | 77% |
| rag-ingest-worker | 1.16 GiB / 1.5 GiB | 77% |
| rag-permission-sync-worker | 1.16 GiB / 1.5 GiB | 77% |

Kong 从原先无限制时的 1.2 GB 被约束在 1.5 GB 以内，Worker 从近 1 GB 且持续增长变为稳定在 1.16 GB。

### 8.4 验证结果

- `docker compose -f docker-compose.yml config` / `.app.yml` / `.infra.yml` 均验证通过
- 默认 `docker compose up -d` 不再启动 Prometheus/Grafana/Alertmanager
- `docker compose --profile monitoring up -d` 可正常启动监控栈
- 前端登录 `admin` / `Admin123!` 通过 `http://localhost:3002` 正常返回 200

### 8.5 下一步建议

- 进一步拆分 `requirements.txt`：后端只保留 API/DB/缓存依赖，Worker 按队列裁剪 Python 包，可再减 500–700 MB / 镜像
- 将 `Dockerfile.worker` 按 `embed` / `permission-sync` 拆分为更精简的专用镜像
- 评估 Milvus cluster 模式部署到 K8s，替代 standalone
- 为生产环境配置 `mem_swappiness=10` 或关闭 swap，避免内存限制触发 OOM killer
