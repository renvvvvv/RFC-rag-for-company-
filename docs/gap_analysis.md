# 项目差距分析报告（2026-06-15 更新）

基于 ToB 产品文档套件 `RAG项目-ToB产品文档套件.html` 与当前代码实现对比。

---

## 一、结论速览

当前项目已完成 **约 75%～80%** 的产品文档套件要求：

- ✅ 基础架构、Docker Compose 全栈、CI/CD 蓝绿部署、DevSecOps 安全扫描门禁、设计文档已比较完整。
- ✅ P0 核心能力中，**混合检索、多轮对话、引用溯源、搜索历史、消息反馈、文档重新处理、知识库统计、用户/用户组 CRUD、关键词扫描、敏感信息检测、评测体系、组件健康检查** 均已实现。
- ⚠️ P0 中 **智能文档解析（OCR / 表格结构化 / 元数据抽取）** 与 **音频解析** 已落地 Pipeline，但部分能力依赖外部私有化依赖（tesseract / Whisper 等），实际效果仍需按部署环境打磨。
- ⚠️ 权限 ACL 已实现五级穿透与缓存，但管理端缺少批量授权、权限继承规则校验等高级功能。
- ❌ P2 能力中，**知识图谱、IM 集成、Agentic RAG、多语言 UI、移动端适配** 仍未实现。
- ❌ 运营与项目交付物（用户手册、FAQ、培训 PPT、测试报告、上线 Checklist 等）仍然缺失。

---

## 二、已实现的亮点

| 维度 | 完成情况 | 关键实现文件 |
|------|----------|--------------|
| 架构与部署 | Docker Compose 全栈（约 15 个服务）、Kong 网关、蓝绿部署脚本、GitHub Actions CI/CD | `docker-compose.yml`、`kong.yml`、`scripts/blue-green-deploy.sh`、`.github/workflows/ci-cd.yml` |
| 数据模型 | users / groups / knowledge_bases / documents / chunks / conversations / messages / permissions / audit_logs / system_config / search_history / evaluation / collaboration | `backend/app/models/` |
| 权限控制 | 文件类型 → 文档 → 字段 → 标签 → 关键词五级穿透，RBAC+ABAC 混合，Redis 缓存 | `backend/app/services/permission_service.py`、`backend/app/api/v1/permissions.py`、`backend/app/core/cache.py` |
| 上下文压缩 | CompressionService 已实现权限标记内联与按级别分组压缩 | `backend/app/services/compression_service.py` |
| API 安全网关 | SecurityGateway 已实现 L4 本地 / L3 脱敏 / L2 直接调用策略，并集成 Prompt Injection 检测 | `backend/app/services/security_gateway.py` |
| 模型配置 | 支持数据库实时读写，无需重启 | `backend/app/core/runtime_config.py`、`backend/app/api/v1/config.py` |
| 混合检索 | 向量检索 + BM25 关键词检索 + RRF 融合 + Cross-Encoder 重排序，支持 hybrid / semantic / keyword 三种模式 | `backend/app/services/retrieval_service.py`、`backend/app/retrieval/{bm25_client,embedding_client,milvus_client,rerank_client}.py` |
| 多轮对话 | 会话与消息表、conversation_id 上下文管理、历史消息构建、流式/非流式问答 | `backend/app/api/v1/chat.py`、`backend/app/services/conversation_service.py`、`backend/app/models/{conversation,message}.py` |
| 文档摄取 | Document / Excel / Image / Video / Link / Audio 6 个 Pipeline + Factory，支持 OCR 回退、表格提取、元数据抽取 | `backend/app/pipelines/` |
| 前端页面 | Login / KnowledgeBase / UploadCenter / SearchConsole / PermissionMgr / SystemAdmin / EvalWorkbench | `frontend/src/pages/` |
| 设计文档 | `docs/design/00-14` 共 15 份，覆盖架构、权限、检索、部署等 | `docs/design/` |
| 监控告警 | Prometheus + Alertmanager + Grafana Dashboard（API / 检索 / 模型 / 总览）已配置 | `monitoring/prometheus/alerts.yml`、`monitoring/grafana/dashboards/`、`monitoring/alertmanager.yml` |
| 安全扫描 | Bandit、Semgrep、pip-audit、Snyk、TruffleHog、Trivy FS/镜像、CodeQL、OWASP ZAP（可选）、SBOM、Prompt Injection 回归测试 | `.github/workflows/ci-cd.yml`、`bandit.yaml`、`trivy.yaml` |

---

## 三、核心功能状态（按 P0/P1/P2）

### 3.1 P0 核心功能 — 已大部落地

| 能力 | 文档套件要求 | 当前实现 | 状态 |
|------|-------------|----------|------|
| **混合检索** | 向量 + BM25 关键词 + Cross-Encoder 重排序 + RRF 融合 | `backend/app/services/retrieval_service.py` 已实现 hybrid / semantic / keyword 三种模式与 RRF 融合 | ✅ |
| **多轮对话** | RAG 多轮对话、conversation_id 上下文管理 | `backend/app/api/v1/chat.py` 与 `conversation_service.py` 已完整实现会话 CRUD、历史消息、消息持久化 | ✅ |
| **引用溯源** | 答案精确引用 chunk/文档 | Chat/Search 返回 `chunk_id`、`doc_id`、`score`、`modality`、`position_info`；Message 表保存 `sources` | ✅（可继续增强到页码级） |
| **搜索历史** | `/search/history` 用户搜索历史 | `backend/app/api/v1/search.py` 已按用户保存并按 mode 过滤返回 | ✅ |
| **消息反馈** | 答案点赞/踩反馈 | `POST /chat/messages/{id}/feedback` 与 `conversation_service.update_feedback` 已实现 | ✅ |
| **用户 CRUD** | 用户的增删改查 | `backend/app/api/v1/users.py` 已完整实现 | ✅ |
| **用户组 CRUD** | 用户组的增删改查、成员管理 | `backend/app/api/v1/groups.py` 已实现 | ✅ |
| **文档重新处理** | `POST /documents/{id}/reprocess` | `backend/app/api/v1/documents.py` 已实现 | ✅ |
| **知识库统计** | `GET /knowledge-bases/{id}/stats` | `backend/app/api/v1/knowledge_bases.py` 已实现文档/分块/状态统计 | ✅ |
| **关键词扫描** | 扫描文本/文档中的敏感关键词 | `POST /keywords/scan` 与 `SensitiveInfoService` 已实现文本与文档 chunk 扫描 | ✅ |
| **敏感信息检测** | PII / 金融 / 医疗 / 自定义敏感信息检测与脱敏 | `backend/app/services/sensitive_info_service.py` 已实现身份证/手机/邮箱/银行卡正则、自定义关键词、可选 spaCy NER、文本脱敏 | ✅ |
| **评测体系** | Recall@K / MRR / NDCG / Faithfulness / Relevance / Coherence | `backend/app/api/v1/eval.py` 与 `evaluation_service.py` 已实现数据集、任务、指标计算、Celery 异步执行 | ✅ |
| **组件健康检查** | `/api/v1/health` 返回各子组件状态 | `backend/app/api/v1/health.py` 已检查 postgres / redis / rabbitmq / milvus / minio 并返回延迟 | ✅ |
| **智能文档解析** | 自动分块、表格提取、图片 OCR、元数据抽取 | `document_pipeline.py` / `excel_pipeline.py` / `image_pipeline.py` 已实现，但 OCR 依赖 tesseract、部分回退提示需私有化安装 | ⚠️ |
| **音频支持** | 支持音频文件解析 | `audio_pipeline.py` 已实现，优先 Whisper、回退 speech_recognition，依赖需私有化安装 | ⚠️ |
| **段落级权限** | 组织-用户组-知识库-文档-段落五级穿透 | `permission_service.py` 已实现字段/标签/关键词/文档/文件类型过滤；段落级通过 chunk 权限过滤与内容降级实现 | ⚠️（管理端待完善） |
| **14 服务编排** | 含多 worker / celery-beat | 当前 `docker-compose.yml` 含 3 个业务 worker，无独立 celery-beat；可复用 worker 或外部调度补齐 | ⚠️ |

### 3.2 P1 重要能力 — 基本具备，部分待完善

| 能力 | 文档套件要求 | 当前实现 | 状态 |
|------|-------------|----------|------|
| **监控告警** | Prometheus + Grafana Dashboard + 告警规则 + Alertmanager | Dashboard（API / 检索 / 模型 / 总览）与告警规则已配置，Alertmanager 基础路由已存在 | ✅（告警通道需替换为真实接收人） |
| **CI 安全扫描** | SAST / SCA / 容器扫描 / SBOM | GitHub Actions 已配置 Bandit、Semgrep、pip-audit、Snyk、TruffleHog、Trivy、CodeQL、ZAP、SBOM | ✅ |
| **Prompt 注入防护** | 输入清洗、指令隔离、输出过滤 | `security_gateway.py` 已实现常见注入模式检测与实体脱敏，并配套回归测试 | ✅ |
| **协作功能** | 文档评论、标注、收藏 | `backend/app/api/v1/collaboration.py` 与 `services/collaboration_service.py` 已实现评论与书签 | ✅ |
| **权限 ACL 管理端** | 批量授权、权限继承、审批流 | 已有 `permissions.py` 基础端点，但缺少批量与继承校验 | ⚠️ |
| **DAST** | OWASP ZAP 动态扫描 | 工作流中仅在配置了 `STAGING_URL` 时触发 | ⚠️ |
| **Startup Probe** | K8s Startup Probe | Docker Compose 使用 `healthcheck`/`start_period`，独立的 K8s Startup Probe 未配置 | ⚠️ |

### 3.3 P2 扩展能力 — 长期建设

| 能力 | 文档套件要求 | 当前实现 | 状态 |
|------|-------------|----------|------|
| **知识图谱** | 实体抽取、关系抽取、图谱检索 | 完全缺失 | ❌ |
| **IM 集成** | 企微 / 飞书 / 钉钉集成 | 完全缺失 | ❌ |
| **Agentic RAG** | Agent 自主规划检索策略、多步推理 | 完全缺失 | ❌ |
| **多语言 UI** | 中英文切换 | 前端未实现 | ❌ |
| **移动端适配** | 响应式/移动端页面 | 未验证 | ❌ |

---

## 四、API 完整度

文档套件中 API 覆盖：知识库、文档、检索、问答、权限、评测、敏感关键词、用户/用户组。

**已实现的 API：**

| API | 实现位置 |
|-----|----------|
| `POST /auth/login` / `/auth/register` / `/auth/me` | `backend/app/api/v1/auth.py` |
| `POST /knowledge-bases` / `GET /knowledge-bases` / `PATCH /knowledge-bases/{id}` / `DELETE /knowledge-bases/{id}` / `GET /knowledge-bases/{id}/stats` | `backend/app/api/v1/knowledge_bases.py` |
| `POST /documents` / `GET /documents/{kb_id}` / `GET /documents/detail/{doc_id}` / `DELETE /documents/detail/{doc_id}` / `POST /documents/{doc_id}/reprocess` | `backend/app/api/v1/documents.py` |
| `POST /search` / `/search/semantic` / `/search/keyword` / `GET /search/history` | `backend/app/api/v1/search.py` |
| `POST /chat` / `/chat/stream` / `/chat/conversations` / `GET /chat/conversations` / `GET /chat/conversations/{id}/messages` / `DELETE /chat/conversations/{id}` / `POST /chat/messages/{id}/feedback` | `backend/app/api/v1/chat.py` |
| `POST /permissions/file-type` / `/permissions/document` / `/permissions/field` / `/permissions/tag` / `GET /permissions/check/{doc_id}` | `backend/app/api/v1/permissions.py` |
| `GET /keywords` / `POST /keywords` / `PUT /keywords/{id}` / `DELETE /keywords/{id}` / `POST /keywords/batch-import` / `POST /keywords/scan` | `backend/app/api/v1/keywords.py` |
| `GET /users` / `GET /users/{id}` / `POST /users` / `PUT /users/{id}` / `DELETE /users/{id}` | `backend/app/api/v1/users.py` |
| `GET /groups` / `POST /groups` / `PUT /groups/{id}` / `DELETE /groups/{id}` / `POST /groups/{id}/members` | `backend/app/api/v1/groups.py` |
| `POST /evaluation/datasets` / `GET /evaluation/datasets` / `POST /evaluation/tasks` / `GET /evaluation/tasks` / `GET /evaluation/tasks/{id}` / `GET /evaluation/metrics` | `backend/app/api/v1/eval.py` |
| `POST /comments` / `GET /comments` / `PUT /comments/{id}` / `DELETE /comments/{id}` / `POST /bookmarks` / `GET /bookmarks` / `DELETE /bookmarks/{id}` | `backend/app/api/v1/collaboration.py` |
| `GET /config/models` / `PUT /config/models` | `backend/app/api/v1/config.py` |
| `GET /health` | `backend/app/api/v1/health.py` |
| `/metrics` | `backend/app/main.py` Prometheus ASGI |

**仍未实现或待完善的 API：**

1. 知识图谱相关 API（实体/关系/图谱检索）
2. IM 机器人回调与消息推送 API
3. Agentic RAG 规划与工具调用 API
4. 多语言切换接口与前端 i18n
5. 运营数据看板 API（用户活跃度、检索热度、问答满意度等）
6. 细粒度审计日志导出与告警 API

---

## 五、安全与 DevSecOps 状态

| 要求 | 当前状态 | 建议 |
|------|----------|------|
| SAST（Semgrep / Bandit / CodeQL） | ✅ GitHub Actions 已配置 | 持续维护规则集 |
| DAST（OWASP ZAP） | ⚠️ 已配置但仅在 `STAGING_URL` 存在时触发 | 配置预发环境后启用 |
| SCA（pip-audit / Snyk） | ✅ 已配置 | 启用 Snyk Token 获取更完整报告 |
| 容器镜像扫描（Trivy） | ✅ build-and-push 阶段已扫描 | 生产环境建议将 `IMAGE_SCAN_FAIL_ON_SEVERITY` 设为 `true` |
| Prompt 注入防护 | ✅ `security_gateway.py` 已提供静态规则与实体脱敏 | 可引入专用输入分类器进一步提升准确率 |
| 敏感信息检测（PII / NER） | ✅ 正则 + 自定义关键词 + 可选 spaCy NER | 私有化部署时安装 `zh_core_web_sm` 并校准阈值 |
| SBOM 生成 | ✅ CI 中通过 Trivy 生成 CycloneDX SBOM | 随 release 归档 SBOM |
| 安全扫描门禁 | ⚠️ 当前仅 pip-audit / Semgrep / prompt-injection 失败会阻断；镜像扫描为告警模式 | 按业务容忍度调整门禁策略 |

---

## 六、监控与可观测性状态

| 要求 | 当前状态 |
|------|----------|
| Prometheus + Grafana 服务 | ✅ 已配置 |
| `/api/v1/health` 组件健康检查 | ✅ 已检查 postgres / redis / rabbitmq / milvus / minio |
| Kong 主动健康检查 | ⚠️ 当前 Kong 使用 `depends_on` 与健康检查，未在 `kong.yml` 中配置主动 upstream healthcheck |
| Grafana Dashboard（API / 检索 / 模型 / 资源） | ✅ `monitoring/grafana/dashboards/` 已提供 4 套预配置 Dashboard |
| 告警规则（P99 / 错误率 / 队列长度 / 磁盘 / 服务存活） | ✅ `monitoring/prometheus/alerts.yml` 已配置 |
| Alertmanager 告警通道 | ⚠️ 配置文件存在，但接收邮箱 / Slack / PagerDuty 为占位值，需替换为真实通道 |
| Liveness / Readiness / Startup Probe | ⚠️ Docker Compose 使用 `healthcheck` + `start_period`；独立的 K8s Startup Probe 未配置 |
| 应用指标中间件 | ✅ `backend/app/main.py` PrometheusMiddleware 已统计请求数与耗时 |

---

## 七、文档与运营交付物缺口

文档套件包含大量 ToB 交付物，当前项目仍然缺失或仅部分覆盖：

| 交付物 | 状态 |
|--------|------|
| 需求调研报告 | ❌ 缺失 |
| 用户画像 Persona | ❌ 缺失 |
| 痛点优先级矩阵 | ❌ 缺失 |
| PRD 产品需求文档 | ⚠️ 设计文档中有部分替代，但无正式 PRD |
| Sprint 计划 | ❌ 缺失 |
| 每日站会记录模板 | ❌ 缺失 |
| 测试报告 | ❌ 缺失 |
| 上线 Checklist | ❌ 缺失 |
| 用户手册 | ❌ 缺失 |
| 培训 PPT 大纲 | ❌ 缺失 |
| FAQ 文档 | ❌ 缺失 |
| API 使用指南 | ✅ 本次新增 `docs/API_USAGE.md` |
| 变更日志 | ✅ 本次新增 `docs/CHANGELOG.md` |
| 运营数据看板 | ⚠️ 前端有 EvalWorkbench，但运营指标看板未明确 |

---

## 八、建议优先级

### 🔴 P0（影响产品可用性，建议 2 周内补齐）

1. 完善权限 ACL 管理端：批量授权、继承规则校验、审批流占位转真实。
2. 按私有化环境补齐 OCR / Whisper / tesseract 依赖，消除文档/音频解析的占位回退。
3. 将 Alertmanager 告警通道替换为真实邮箱 / Slack / PagerDuty / 企业微信 webhook。
4. 补充 K8s Startup Probe 与 Kong upstream 主动健康检查。
5. 将镜像扫描 `IMAGE_SCAN_FAIL_ON_SEVERITY` 按生产要求启用。

### 🟠 P1（影响产品竞争力，建议 1 个月内补齐）

6. 配置预发环境并启用 OWASP ZAP DAST。
7. 增强引用溯源：在 `SourceItem` 中补充页码 / sheet / row_range 等精确位置信息。
8. 引入 Prompt Injection 专用分类器，降低静态规则误报。
9. 补齐运营数据看板：检索热度、问答满意度、用户活跃度等。
10. 完善审计日志导出与告警接口。

### 🔵 P2（长期差异化能力）

11. 知识图谱模块（实体/关系抽取、图谱检索）
12. 企微 / 飞书 / 钉钉 IM 集成
13. Agentic RAG 探索（检索策略规划、多步推理）
14. 多语言 UI（i18n）与移动端响应式适配

### 🟢 运营交付物（ToB 签单必备）

15. 用户手册、FAQ、培训 PPT
16. 测试报告、上线 Checklist
17. 需求调研报告、Persona、痛点优先级矩阵

---

## 九、附录：快速核对清单

```text
✅ 混合检索 API 可用
✅ BM25 / 关键词检索实现
✅ RRF 融合实现
✅ 多轮对话 API 可用
✅ 答案引用溯源到 chunk
⚠️ 文档 OCR / 表格提取（依赖环境）
⚠️ 音频解析（依赖环境）
✅ 评测任务 API 可用
✅ 敏感信息检测 API 可用
✅ Grafana Dashboard 导入即用
⚠️ Alertmanager 告警通道需替换为真实接收人
✅ CI 安全扫描门禁
❌ 用户手册
❌ FAQ 文档
❌ 培训 PPT
❌ 测试报告
❌ 上线 Checklist
```
