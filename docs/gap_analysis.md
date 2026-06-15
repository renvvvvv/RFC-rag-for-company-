# 项目差距分析报告

基于 ToB 产品文档套件 `RAG项目-ToB产品文档套件.html` 与当前代码实现对比。

## 一、结论速览

当前项目已完成 **约 55%～60%** 的产品文档套件要求：

- ✅ 基础架构、Docker 全栈、CI/CD 蓝绿部署、设计文档已比较完整
- ⚠️ P0 核心能力中，**混合检索、多轮对话、智能解析、音频支持** 尚未落地
- ⚠️ P1 能力中，**评测体系、敏感信息检测、完整监控告警** 仅做了 placeholder
- ❌ P2 能力中，**知识图谱、评论标注、企微/飞书/钉钉集成、Agentic RAG** 完全缺失
- ❌ 运营与项目交付物（用户手册、FAQ、培训 PPT、测试报告、上线 Checklist 等）基本缺失

---

## 二、已实现的亮点

| 维度 | 完成情况 |
|------|----------|
| 架构与部署 | Docker Compose 全栈（约 15 个服务）、蓝绿部署脚本、GitHub Actions CI/CD |
| 数据模型 | users / groups / knowledge_bases / documents / chunks / permissions / audit_logs / system_config 等核心表 |
| 权限控制 | 文件类型 → 文档 → 字段 → 标签 → 关键词 五级穿透，RBAC+ABAC 混合 |
| 上下文压缩 | CompressionService 已实现权限标记内联与按级别分组压缩 |
| API 安全网关 | SecurityGateway 已实现 L4 本地 / L3 脱敏 / L2 直接调用策略 |
| 模型配置 | 支持数据库实时读写，无需重启 |
| 前端页面 | Login / KnowledgeBase / UploadCenter / SearchConsole / PermissionMgr / SystemAdmin / EvalWorkbench |
| 文档摄取 | Document / Excel / Image / Video / Link 5 个 Pipeline + Factory |
| 设计文档 | `docs/design/00-14` 共 15 份，覆盖架构、权限、检索、部署等 |

---

## 三、核心功能缺口（按 P0/P1/P2）

### 3.1 P0 核心功能 — 立即需要补齐

| 能力 | 文档套件要求 | 当前实现 | 差距 |
|------|-------------|----------|------|
| **混合检索** | 向量 + BM25 关键词 + 知识图谱 + Cross-Encoder 重排序 + RRF 融合 | `backend/app/api/v1/search.py` 是 placeholder；`RetrievalService` 仅实现向量检索 + Re-rank | **大**。缺少 BM25、知识图谱、RRF 融合 |
| **智能文档解析** | 自动分块、表格提取、图片 OCR、元数据抽取 | Pipelines 较简单，仅基础解析，无 OCR/表格结构化 | **大** |
| **多轮对话** | RAG 多轮对话、conversation_id 上下文管理 | `chat.py` 单轮问答，无对话历史与上下文 | **大** |
| **引用溯源** | 答案精确引用 chunk/文档/页码 | chat 返回 sources 结构较粗 | 中 |
| **音频支持** | 支持音频文件解析 | 无 `audio_pipeline` | 中 |
| **段落级权限** | 组织-用户组-知识库-文档-段落五级穿透 | 已实现字段/关键词级过滤，但段落级细粒度仍需强化 | 中 |
| **14 服务编排** | 含 celery-worker-1/2、celery-beat | 当前只有 3 个 worker，无 celery-beat | 小 |

### 3.2 P1 重要能力 — 计划补齐

| 能力 | 文档套件要求 | 当前实现 | 差距 |
|------|-------------|----------|------|
| **评测体系** | Recall@K / MRR / NDCG / Faithfulness / Relevance / Coherence | `backend/app/api/v1/eval.py` 是 placeholder | **大** |
| **敏感信息检测** | PII / 金融 / 医疗 / 自定义敏感信息检测与脱敏 | 仅有敏感关键词管理，无 NER/正则扫描服务 | **大** |
| **监控告警** | Prometheus + Grafana Dashboard + 告警规则 | 服务已启动，但 dashboard、告警阈值、告警通道未落地 | 中 |
| **关键词扫描** | 扫描文本/文档中的敏感关键词 | 缺少 `/keywords/scan` 实现 | 中 |
| **检索历史** | `/search/history` 用户搜索历史 | 未实现 | 小 |
| **消息反馈** | 答案点赞/踩反馈 | 未实现 | 小 |

### 3.3 P2 扩展能力 — 长期建设

| 能力 | 文档套件要求 | 当前实现 | 差距 |
|------|-------------|----------|------|
| **知识图谱** | 实体抽取、关系抽取、图谱检索 | 完全缺失 | **大** |
| **协作功能** | 文档评论、标注、收藏 | 完全缺失 | **大** |
| **IM 集成** | 企微 / 飞书 / 钉钉集成 | 完全缺失 | **大** |
| **Agentic RAG** | Agent 自主规划检索策略、多步推理 | 完全缺失 | **大** |
| **多语言 UI** | 中英文切换 | 前端未实现 | 中 |
| **移动端适配** | 响应式/移动端页面 | 未验证 | 中 |

---

## 四、API 完整度缺口

文档套件中 API 覆盖：知识库、文档、检索、问答、权限、评测、敏感关键词、用户/用户组。

当前缺口：

1. `POST /search` — **placeholder**，未实现混合检索
2. `POST /search/semantic` / `/search/keyword` — 未实现
3. `GET /search/history` — 未实现
4. `GET /chat/conversations` / `messages` — 未实现多轮对话
5. `POST /chat/messages/{id}/feedback` — 未实现反馈
6. `POST /evaluation/*` — **placeholder**，未实现评测任务
7. `POST /evaluation/datasets` — 未实现
8. `POST /sensitive-keywords/scan` — 未实现
9. `POST /users` / `PUT /users/{id}` / `DELETE /users/{id}` — `users.py` 只有列表/详情
10. `POST /permissions/grant` / `revoke` / `check` — 当前实现较简化，缺少完整 ACL
11. `GET /knowledge-bases/{id}/stats` — 未实现
12. `POST /documents/{id}/reprocess` — 未实现

---

## 五、安全与 DevSecOps 缺口

文档套件要求：

| 要求 | 当前状态 | 建议 |
|------|----------|------|
| SAST（Semgrep/Bandit/CodeQL） | 未配置 | 在 GitHub Actions 中加入 |
| DAST（OWASP ZAP/Nuclei） | 未配置 | Staging 环境部署后扫描 |
| SCA（Snyk/Safety/Trivy） | 未配置 | Python 依赖扫描 |
| 容器镜像扫描（Trivy） | 未配置 | CI build-and-push 阶段加入 |
| Prompt 注入防护 | 有概念设计，无实现 | 增加输入清洗、指令隔离、输出过滤 |
| 敏感信息检测（PII/NER） | 未实现 | 增加文档上传扫描与问答输出过滤 |
| SBOM 生成 | 未配置 | CI 中生成并上传 |
| 安全扫描门禁 | 未配置 | CI 中设置高危漏洞阻断 |

---

## 六、监控与可观测性缺口

| 要求 | 当前状态 |
|------|----------|
| Prometheus + Grafana 服务 | ✅ 已配置 |
| `/api/v1/health` 组件健康检查 | ⚠️ 基础实现，缺少 milvus/minio/rabbitmq 等子组件状态 |
| Kong 主动健康检查 | ⚠️ 配置较简单 |
| Grafana Dashboard（API/检索/模型/资源） | ❌ 未落地 |
| 告警规则（P99/P95/错误率/队列长度） | ❌ 未落地 |
| Alertmanager 告警通道 | ❌ 未落地 |
| Liveness/Readiness/Startup Probe | ⚠️ Liveness/Readiness 有，Startup Probe 缺失 |

---

## 七、文档与运营交付物缺口

文档套件包含大量 ToB 交付物，当前项目基本缺失：

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
| 运营数据看板 | ⚠️ 前端有 EvalWorkbench，但运营指标看板未明确 |

---

## 八、建议优先级

### 🔴 P0（影响产品可用性，建议 2 周内补齐）

1. 实现真正的 `/search` 混合检索：向量 + BM25 + RRF + Cross-Encoder
2. 实现多轮对话 API：`conversations` / `messages` / `feedback`
3. 补齐用户 CRUD、文档重新处理、知识库统计等 API
4. 增加文档解析能力：OCR、表格提取、元数据抽取
5. 完善健康检查 `/health`，返回各组件真实状态

### 🟠 P1（影响产品竞争力，建议 1 个月内补齐）

6. 落地评测体系：`/evaluation/tasks` + 指标计算
7. 落地敏感信息检测：PII/NER + `/keywords/scan`
8. 配置完整监控告警：Grafana Dashboard + Alertmanager
9. CI/CD 中加入 SAST/SCA/容器扫描
10. 增加音频解析 Pipeline

### 🔵 P2（长期差异化能力）

11. 知识图谱模块
12. 企微/飞书/钉钉集成
13. 文档评论/标注/收藏
14. Agentic RAG 探索

### 🟢 运营交付物（ToB 签单必备）

15. 用户手册、FAQ、培训 PPT
16. 测试报告、上线 Checklist
17. 运营数据看板

---

## 九、附录：快速核对清单

```text
□ 混合检索 API 可用
□ BM25 / 关键词检索实现
□ RRF 融合实现
□ 多轮对话 API 可用
□ 答案引用溯源精确到 chunk
□ 文档 OCR / 表格提取
□ 音频解析
□ 评测任务 API 可用
□ 敏感信息检测 API 可用
□ Grafana Dashboard 导入即用
□ Alertmanager 告警配置
□ CI 安全扫描门禁
□ 用户手册完成
□ FAQ 文档完成
□ 培训 PPT 完成
□ 测试报告完成
□ 上线 Checklist 完成
```
