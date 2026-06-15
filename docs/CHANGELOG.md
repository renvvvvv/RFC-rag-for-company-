# 变更日志

## 2026-06-15

### 新增与完善

- **权限 ACL 完善**：
  - `backend/app/services/permission_service.py` 实现默认拒绝（default-deny）逻辑，支持文件类型、文档、字段（Word / Excel）、标签、关键词五级权限穿透。
  - 字段权限新增 `config` JSONB 列，用于存储 Excel sheet/column 或 Word bookmark 等细粒度配置（Alembic 手写迁移 `2026_06_15_2315-add_field_permission_config.py`）。
  - 授权时自动清空目标用户/用户组缓存；支持逗号分隔的批量标签授权。
- **引用溯源增强**：
  - `backend/app/api/v1/chat.py` 流式接口将检索结果 `sources` 持久化到 `Message.sources`。
  - 返回字段包含 `chunk_id`、`doc_id`、`content`、`score`、`modality`、`position_info`。
- **流式敏感关键词拦截**：
  - `backend/app/services/generation_service.py` 在全局单例 `KeywordAnnotator` 中加载关键词，流式输出过程中命中敏感词即返回截断提示。
  - `backend/app/main.py` 启动时从数据库加载关键词并初始化 annotator；关键词变更后通过关键词管理接口重置。
- **前端 API 对齐与构建修复**：
  - `frontend/src/pages/SearchConsole.tsx` 所有后端请求路径补全尾斜杠 `/`，匹配 FastAPI router 声明。
  - 修复 TypeScript `any` 类型导致的 lint 警告；`EvalWorkbench.tsx` 中 `any` 改为 `unknown`/`string`。
  - `pnpm lint && pnpm build` 通过。
- **文档与示例对齐**：
  - `docs/API_USAGE.md` 所有 curl 示例路径统一加上尾斜杠，与 FastAPI 路由保持一致；修复 JSON 示例中缺失 `{` 的语法错误。
  - `docs/gap_analysis.md` 更新 P0/P1 完成功能清单，将权限 ACL、引用溯源、前端 API 对齐标记为已完成。
- **测试修复**：
  - 修复 `tests/test_permissions.py::TestPermissionServiceGrant::test_grant_file_type_to_group` 失败：当 `group_service.get_group` 在测试 mock 下返回 coroutine 时，缓存失效逻辑捕获 `AttributeError`。
  - 当前后端测试：`129 passed, 14 warnings`。

### 已确认的已实现能力

- 混合检索（向量 + BM25 + RRF + Cross-Encoder 重排序）
- 多轮对话与会话管理
- 消息点赞/踩反馈
- 搜索历史
- 文档重新处理
- 知识库统计
- 用户与用户组 CRUD
- 敏感关键词扫描
- 敏感信息检测（PII 正则 + 自定义关键词 + 可选 NER）
- 评测体系（数据集、任务、Recall@K / MRR / NDCG / Faithfulness / Relevance / Coherence）
- 监控告警（Prometheus + Grafana Dashboard + Alertmanager + 告警规则）
- 协作功能（评论、书签）
- 权限 ACL（文件类型、文档、字段、标签、关键词）
- 流式输出敏感关键词拦截
- DevSecOps（Bandit、Semgrep、pip-audit、Snyk、TruffleHog、Trivy、CodeQL、SBOM、Prompt Injection 回归测试）

### 仍待建设的长期能力

- 知识图谱（实体/关系抽取、图谱检索）
- 企微 / 飞书 / 钉钉 IM 集成
- Agentic RAG（检索策略规划、多步推理）
- 多语言 UI（i18n）
- 移动端响应式适配
- 运营交付物（用户手册、FAQ、培训 PPT、测试报告、上线 Checklist 等）
