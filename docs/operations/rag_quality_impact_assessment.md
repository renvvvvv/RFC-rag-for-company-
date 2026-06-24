# 轻量化改造对 RAG 效果的影响评估

> 评估对象：用 pgvector 替代 Milvus、本地存储替代 MinIO、Redis 替代 RabbitMQ 的轻量化方案
> 评估日期：2026-06-24

---

## 1. 一句话结论

**对权限 RAG 管理系统的核心效果影响很小，但在超大规模（>100 万文档）和高并发写入场景下会有性能损失。**

具体而言：
- ✅ **检索质量**：< 10 万文档时，pgvector HNSW 与 Milvus HNSW 几乎无差别
- ✅ **权限过滤**：pgvector 与 PostgreSQL 原生结合，反而更自然高效
- ✅ **关键词搜索**：基于 Postgres 全文检索，不受影响
- ✅ **重排序**：外部 rerank 服务，不受影响
- ⚠️ **扩展性**：> 100 万文档后，Milvus 在索引构建、并发写入、分布式扩展上优势明显
- ⚠️ **多模态/图片**：pgvector 可支持，但 Milvus 的专用索引和 GPU 加速在超大规模图片库更优

---

## 2. 当前 RAG 链路拆解

```
用户查询
  ├── 权限过滤条件生成（PostgreSQL）
  ├── 向量检索（Milvus）─── 可被 pgvector 替代
  ├── BM25 关键词检索（PostgreSQL 全文检索）
  ├── RRF 结果融合（Python）
  ├── 加载 Chunk 详情（PostgreSQL）
  ├── 字段级权限 + 关键词级别过滤（Python）
  └── 重排序（外部 rerank API）
```

**关键发现**：向量检索只是 RAG 链路中的一环，且最终回答质量还依赖 BM25、RRF 融合和重排序。即使向量检索略有下降，整体效果也被其他环节缓冲。

---

## 3. Milvus vs pgvector 详细对比

### 3.1 功能等价性

| 能力 | Milvus | pgvector | 影响 |
|------|--------|----------|------|
| 稠密向量 ANN 搜索 | HNSW / IVF | HNSW / IVFFlat | ✅ 等价 |
| 余弦相似度 | 支持 | 支持 (`<=>`) | ✅ 等价 |
| 元数据过滤 | `expr` 表达式 | SQL `WHERE` | ✅ pgvector 更自然 |
| 权限过滤 | 序列化 filter_expr | 原生 SQL join | ✅ pgvector 更高效 |
| 向量 + 标量混合查询 | 支持 | 支持 | ✅ 等价 |
| 图片向量（512-dim） | 支持 | 支持 | ✅ 等价 |
| 批量写入吞吐 | 高 | 中 | ⚠️ 大流量写入时 pgvector 较慢 |
| 分布式扩展 | 优秀 | 需 Citus/分片 | ⚠️ 海量数据受限 |
| GPU 加速 | 支持 | 不支持 | ⚠️ 超大模型/图片库受影响 |
| 动态字段 | 支持 | 需固定 schema | ⚠️ 代码需调整 |

### 3.2 性能对比（经验值）

| 场景 | Milvus standalone | pgvector HNSW | 差异 |
|------|-------------------|---------------|------|
| 1 万文档检索 | ~2 ms | ~3 ms | 无感知 |
| 10 万文档检索 | ~3 ms | ~8 ms | 无感知 |
| 100 万文档检索 | ~5 ms | ~30 ms | 可感知 |
| 1000 万文档检索 | ~10 ms | ~200 ms+ | 明显差距 |
| 批量写入 10 万向量 | ~10 s | ~60 s | 差距大 |
| 索引构建 100 万向量 | ~2 min | ~10 min | 差距大 |

> 注：以上数值为典型场景经验值，实际受硬件、维度、索引参数影响。

### 3.3 本项目使用特征

当前代码中 Milvus 的使用：
- 文本块向量：768 维，COSINE，HNSW 索引
- 图片关键帧向量：512 维，COSINE，HNSW 索引
- 查询时带 `filter_expr` 做 kb_id/modality/status 过滤
- 无稀疏向量、无分区、无动态字段复杂操作
- 无 GPU 相关代码

**结论**：pgvector 完全可以覆盖当前代码的需求。

---

## 4. 各模块影响评估

### 4.1 权限 RAG 核心功能

| 功能 | 影响 | 说明 |
|------|------|------|
| 用户分级（L0–L4） | 无影响 | 纯 PostgreSQL |
| 知识库管理 | 无影响 | 纯 PostgreSQL |
| 文档上传 | 轻微影响 | 本地存储替代 MinIO，功能等价 |
| 文档解析 | 无影响 | 依赖 unstructured，与向量库无关 |
| 向量化 | 无影响 | 依赖外部 Embedding API |
| 权限检索 | **略有改善** | pgvector + SQL 过滤更直接 |
| 安全网关 | 无影响 | 关键词级别判断，与向量库无关 |
| API Key | 无影响 | 纯 PostgreSQL + Redis |
| RAG Chat | 几乎无影响 | 最终效果由 hybrid + rerank 决定 |

### 4.2 检索模式影响

| 模式 | 影响 | 原因 |
|------|------|------|
| `semantic`（纯向量） | 轻微下降 | pgvector ANN 略慢于 Milvus，但质量接近 |
| `keyword`（纯 BM25） | 无影响 | 基于 PostgreSQL 全文检索 |
| `hybrid`（默认） | 几乎无影响 | RRF 融合 + rerank 缓冲了向量侧差异 |

### 4.3 可观测指标影响

| 指标 | Milvus | pgvector |
|------|--------|----------|
| 召回率（Recall@10） | ~95% | ~93%（HNSW ef=64） |
| 精确率 | 相当 | 相当 |
| 检索延迟（P95） | 低 | 略高 |
| 索引时间 | 快 | 慢 |

> 召回率 93% vs 95% 对最终 RAG 回答质量影响很小，因为 top_k 会放大到 20，再经 rerank 取前 5。

---

## 5. 损失可控的边界条件

### 5.1 可以放心用 pgvector 的场景

- 文档量 < 10 万
- 并发查询 < 100 QPS
- 向量维度 768 / 512（标准 Embedding 模型）
- 不需要实时海量写入
- 不需要跨节点水平扩展向量库

### 5.2 应该保留 Milvus 的场景

- 文档量 > 100 万
- 高并发写入（如批量导入万级文档）
- 需要图片/视频向量库单独扩展
- 未来计划 K8s 多节点扩展
- 需要 GPU 加速索引构建

---

## 6. 进一步降低影响的建议

如果担心 pgvector 影响效果，可以采取以下措施：

1. **提高 pgvector HNSW 参数**
   ```sql
   CREATE INDEX ON text_chunks USING hnsw (embedding vector_cosine_ops)
   WITH (m = 16, ef_construction = 200);
   SET hnsw.ef_search = 128;  -- 默认 64，提高召回率
   ```

2. **增大 hybrid 模式的 top_k**
   - 当前 `top_k * 2 = 20`，可调整为 30–50，用 RRF + rerank 弥补召回

3. **保留 BM25 权重**
   - 关键词搜索不受向量库影响，适当增加 keyword 分支权重

4. **监控检索指标**
   - 记录 `rag_retrieval_duration_seconds`
   - 定期抽样评估召回率，超过阈值时切换回 Milvus

5. **混合部署**
   - 轻量化用 pgvector
   - 数据量增长后，`pg_dump` 向量表到 Milvus，切回全量化模式

---

## 7. 综合结论

| 问题 | 答案 |
|------|------|
| RAG 效果会损失吗？ | **基本不会**，尤其 <10 万文档时 |
| 没有 Milvus 影响大吗？ | **不大**，pgvector 能等价替代当前用法 |
| 什么时候必须 Milvus？ | **100 万文档以上或高并发写入** |
| 最安全的做法？ | 双模式：轻量用 pgvector，生产超大规模切 Milvus |

**推荐策略**：
- 开发 / POC / 小企业：用 `docker-compose.lightweight.yml`（pgvector）
- 中大型生产：用 `docker-compose.yml`（Milvus）
- 这样既能享受轻量化的低资源占用，又能在必要时保留 Milvus 的扩展能力。
