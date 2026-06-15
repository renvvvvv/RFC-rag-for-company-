# 核心 API 使用指南

本文档整理企业级私有化多模态 RAG 系统的核心 API 使用示例，适用于后端直连或经 Kong 网关访问。

- 后端直连基址：`http://localhost:8080/api/v1`
- Kong 网关基址：`http://localhost:8000/api/v1`
- 认证方式：OAuth2 Password 登录后，在请求头中携带 `Authorization: Bearer <access_token>`

> 下文所有示例均假设已通过 Kong 网关访问：`http://localhost:8000/api/v1`。

---

## 目录

1. [认证](#1-认证)
2. [知识库](#2-知识库)
3. [文档上传](#3-文档上传)
4. [搜索](#4-搜索)
5. [聊天（非流式）](#5-聊天非流式)
6. [聊天（SSE 流式）](#6-聊天-sse-流式)
7. [评测](#7-评测)
8. [权限](#8-权限)
9. [敏感关键词扫描](#9-敏感关键词扫描)

---

## 1. 认证

### 1.1 登录获取 Token

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=secret"
```

**响应示例：**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "username": "alice",
    "email": "alice@example.com",
    "display_name": "Alice Li",
    "department": "Engineering",
    "security_level": "L2",
    "role_id": null,
    "status": "active",
    "is_active": true
  }
}
```

### 1.2 获取当前用户信息

```bash
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X GET "http://localhost:8000/api/v1/auth/me/" \
  -H "Authorization: Bearer ${TOKEN}"
```

---

## 2. 知识库

### 2.1 创建知识库

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge-bases/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '
    "name": "企业制度知识库",
    "description": "存放公司内部制度、规范与操作手册",
    "config": {
      "chunk_size": 500,
      "overlap": 100,
      "default_modalities": ["text", "table", "image", "link"]
    }
  }'
```

**响应示例：**

```json
{
  "id": "11111111-2222-3333-4444-555555555555",
  "name": "企业制度知识库",
  "description": "存放公司内部制度、规范与操作手册",
  "owner_id": null,
  "config": {
    "chunk_size": 500,
    "overlap": 100,
    "default_modalities": ["text", "table", "image", "link"]
  },
  "status": "active",
  "created_at": "2026-06-15T08:00:00Z"
}
```

### 2.2 查看知识库统计

```bash
curl -X GET "http://localhost:8000/api/v1/knowledge-bases/11111111-2222-3333-4444-555555555555/stats/" \
  -H "Authorization: Bearer ${TOKEN}"
```

**响应示例：**

```json
{
  "kb_id": "11111111-2222-3333-4444-555555555555",
  "document_count": 12,
  "chunk_count": 156,
  "status_breakdown": {
    "completed": 10,
    "processing": 1,
    "failed": 1
  },
  "last_upload_at": "2026-06-14T18:30:00Z"
}
```

---

## 3. 文档上传

### 3.1 上传文件到指定知识库

```bash
curl -X POST "http://localhost:8000/api/v1/documents/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "kb_id=11111111-2222-3333-4444-555555555555" \
  -F "file=@/path/to/员工手册.pdf" \
  -F "tags=制度,HR"
```

**响应示例：**

```json
{
  "id": "66666666-7777-8888-9999-000000000000",
  "kb_id": "11111111-2222-3333-4444-555555555555",
  "filename": "员工手册.pdf",
  "file_type": "pdf",
  "file_size": 204800,
  "mime_type": "application/pdf",
  "storage_key": "11111111-2222-3333-4444-555555555555/xxxx-员工手册.pdf",
  "status": "pending",
  "processing_info": {
    "tags": ["制度", "HR"]
  },
  "metadata": {},
  "created_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "created_at": "2026-06-15T08:05:00Z"
}
```

文档上传后会异步触发摄取任务，状态会从 `pending` → `processing` → `completed` / `failed`。

### 3.2 重新处理文档

```bash
curl -X POST "http://localhost:8000/api/v1/documents/66666666-7777-8888-9999-000000000000/reprocess/" \
  -H "Authorization: Bearer ${TOKEN}"
```

---

## 4. 搜索

系统支持三种检索模式：`hybrid`（向量 + BM25 + RRF + 重排序）、`semantic`（纯向量）、`keyword`（纯 BM25）。

### 4.1 混合检索

```bash
curl -X POST "http://localhost:8000/api/v1/search/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '
    "query": "年假申请流程",
    "kb_ids": ["11111111-2222-3333-4444-555555555555"],
    "mode": "hybrid",
    "modalities": ["text", "table"],
    "top_k": 10,
    "rerank_top_k": 5
  }'
```

**响应示例：**

```json
{
  "query": "年假申请流程",
  "mode": "hybrid",
  "total": 5,
  "results": [
    {
      "chunk_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "doc_id": "66666666-7777-8888-9999-000000000000",
      "content": "员工申请年假需提前 3 天在 OA 提交请假单...",
      "modality": "text",
      "score": 0.3125,
      "rerank_score": 0.92,
      "max_keyword_level": "L1",
      "filtered": false,
      "position_info": {
        "paragraph_range": [1200, 1700]
      },
      "tags": ["制度", "HR"]
    }
  ]
}
```

### 4.2 搜索历史

```bash
curl -X GET "http://localhost:8000/api/v1/search/history/?limit=10&mode=hybrid" \
  -H "Authorization: Bearer ${TOKEN}"
```

**响应示例：**

```json
{
  "total": 2,
  "items": [
    {
      "id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
      "query": "年假申请流程",
      "mode": "hybrid",
      "kb_ids": ["11111111-2222-3333-4444-555555555555"],
      "result_count": 5,
      "created_at": "2026-06-15T08:10:00Z"
    }
  ]
}
```

---

## 5. 聊天（非流式）

### 5.1 单轮问答

```bash
curl -X POST "http://localhost:8000/api/v1/chat/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何申请年假？",
    "kb_ids": ["11111111-2222-3333-4444-555555555555"],
    "top_k": 10,
    "rerank_top_k": 5,
    "max_context_tokens": 4000
  }'
```

**响应示例：**

```json
{
  "answer": "根据《员工手册》，员工需提前 3 天在 OA 系统提交年假申请，并经直属领导审批。",
  "intercepted": false,
  "sources": [
    {
      "doc_id": "66666666-7777-8888-9999-000000000000",
      "chunk_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "content": "员工申请年假需提前 3 天在 OA 提交请假单...",
      "score": 0.92,
      "modality": "text"
    }
  ],
  "strategy": {
    "strategy": "direct_api",
    "max_level": 1,
    "reason": "可直接调用外部API"
  },
  "conversation_id": null
}
```

### 5.2 多轮对话

先创建会话，再用 `conversation_id` 继续对话。

```bash
# 创建会话
curl -X POST "http://localhost:8000/api/v1/chat/conversations/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '
    "title": "年假咨询",
    "kb_ids": ["11111111-2222-3333-4444-555555555555"]
  }'
```

**响应示例：**

```json
{
  "id": "cccccccc-dddd-eeee-ffff-000000000001",
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "年假咨询",
  "kb_ids": ["11111111-2222-3333-4444-555555555555"],
  "created_at": "2026-06-15T08:15:00Z",
  "updated_at": "2026-06-15T08:15:00Z"
}
```

```bash
# 在会话中继续提问
curl -X POST "http://localhost:8000/api/v1/chat/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '
    "query": "那病假呢？",
    "conversation_id": "cccccccc-dddd-eeee-ffff-000000000001"
  }'
```

### 5.3 消息反馈

```bash
curl -X POST "http://localhost:8000/api/v1/chat/messages/xxxxxxxx-yyyy-zzzz-aaaa-bbbbbbbbbbbb/feedback/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '
    "rating": 1,
    "comment": "回答准确，引用了正确制度"
  }'
```

`rating` 取值：`1` 点赞，`-1` 点踩，`0` 中立。

---

## 6. 聊天（SSE 流式）

流式接口为 `POST /chat/stream`，返回 `text/event-stream`。需要携带 `Accept: text/event-stream` 头，并保持连接（使用 `-N` 禁用 curl 输出缓冲）。

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/stream/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '
    "query": "介绍一下报销流程",
    "kb_ids": ["11111111-2222-3333-4444-555555555555"]
  }'
```

**响应示例（SSE 事件流）：**

```text
data: 根据

data: 《财务报销制度》

data: ，员工需先

data: 在 OA 填写报销单

data: 并上传发票。

data: [检测�到敏感内容，输出已截断]

```

> 前端可使用浏览器原生 `EventSource` 或封装库订阅事件。注意：由于需要自定义 `Authorization` 头与 `POST` 请求，`EventSource` 无法直接携带 Token，通常通过 `fetch` + `ReadableStream` 或 `@microsoft/fetch-event-source` 等库实现。

---

## 7. 评测

### 7.1 创建评测数据集

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/datasets/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '
    "kb_id": "11111111-2222-3333-4444-555555555555",
    "name": "年假制度评测集",
    "questions": [
      "年假申请需要提前几天？",
      "未休年假是否可以折现？"
    ],
    "ground_truths": [
      { "chunk_ids": ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"], "answer": "需提前 3 天" },
      { "chunk_ids": ["bbbbbbbb-cccc-dddd-eeee-ffffffffffff"], "answer": "未休年假按国家规定折现" }
    ]
  }'
```

**响应示例：**

```json
{
  "id": "dddddddd-eeee-ffff-0000-111111111111",
  "kb_id": "11111111-2222-3333-4444-555555555555",
  "name": "年假制度评测集",
  "questions": ["年假申请需要提前几天？", "未休年假是否可以折现？"],
  "ground_truths": [
    { "chunk_ids": ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"], "answer": "需提前 3 天" },
    { "chunk_ids": ["bbbbbbbb-cccc-dddd-eeee-ffffffffffff"], "answer": "未休年假按国家规定折现" }
  ],
  "created_at": "2026-06-15T08:20:00Z"
}
```

### 7.2 提交评测任务

```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/tasks/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '
    "dataset_id": "dddddddd-eeee-ffff-0000-111111111111",
    "kb_id": "11111111-2222-3333-4444-555555555555",
    "metrics": ["recall@3", "mrr", "ndcg@3", "faithfulness", "relevance", "coherence"]
  }'
```

**响应示例：**

```json
{
  "id": "eeeeeeee-ffff-0000-1111-222222222222",
  "dataset_id": "dddddddd-eeee-ffff-0000-111111111111",
  "kb_id": "11111111-2222-3333-4444-555555555555",
  "status": "pending",
  "metrics": ["recall@3", "mrr", "ndcg@3", "faithfulness", "relevance", "coherence"],
  "results": {},
  "created_at": "2026-06-15T08:21:00Z",
  "completed_at": null
}
```

### 7.3 查询评测结果

```bash
curl -X GET "http://localhost:8000/api/v1/evaluation/tasks/eeeeeeee-ffff-0000-1111-222222222222/" \
  -H "Authorization: Bearer ${TOKEN}"
```

**响应示例（任务完成后）：**

```json
{
  "id": "eeeeeeee-ffff-0000-1111-222222222222",
  "dataset_id": "dddddddd-eeee-ffff-0000-111111111111",
  "kb_id": "11111111-2222-3333-4444-555555555555",
  "status": "completed",
  "metrics": ["recall@3", "mrr", "ndcg@3", "faithfulness", "relevance", "coherence"],
  "results": {
    "aggregated": {
      "recall@3": 0.75,
      "mrr": 0.8333,
      "ndcg@3": 0.8125,
      "faithfulness": 0.88,
      "relevance": 0.91,
      "coherence": 0.95,
      "sample_count": 2
    },
    "metrics": ["recall@3", "mrr", "ndcg@3", "faithfulness", "relevance", "coherence"]
  },
  "created_at": "2026-06-15T08:21:00Z",
  "completed_at": "2026-06-15T08:25:00Z"
}
```

### 7.4 查看支持的评测指标

```bash
curl -X GET "http://localhost:8000/api/v1/evaluation/metrics/" \
  -H "Authorization: Bearer ${TOKEN}"
```

---

## 8. 权限

### 8.1 设置文档权限

```bash
curl -X POST "http://localhost:8000/api/v1/permissions/document/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "group",
    "target_id": "ffffffff-0000-1111-2222-333333333333",
    "doc_id": "66666666-7777-8888-9999-000000000000",
    "permission": "READ"
  }'
```

`permission` 可选：`NONE` / `READ` / `WRITE` / `ADMIN`。

**响应示例：**

```json
{ "message": "文档权限设置成功" }
```

### 8.2 设置字段级权限（Excel）

```bash
curl -X POST "http://localhost:8000/api/v1/permissions/field/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "group",
    "target_id": "ffffffff-0000-1111-2222-333333333333",
    "doc_id": "66666666-7777-8888-9999-000000000000",
    "file_type": "excel",
    "excel_config": {
      "sheet_permissions": {
        "Sheet1": {
          "access_level": "PARTIAL",
          "allowed_columns": ["姓名", "部门"],
          "denied_columns": ["身份证号", "银行卡号"]
        }
      }
    }
  }'
```

### 8.3 检查用户对文档的权限

```bash
curl -X GET "http://localhost:8000/api/v1/permissions/check/66666666-7777-8888-9999-000000000000/" \
  -H "Authorization: Bearer ${TOKEN}"
```

**响应示例：**

```json
{
  "doc_id": "66666666-7777-8888-9999-000000000000",
  "permission": "READ",
  "security_level": "L2"
}
```

---

## 9. 敏感关键词扫描

### 9.1 扫描自由文本

```bash
curl -X POST "http://localhost:8000/api/v1/keywords/scan/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "请联系我 13800138000，身份证号 110101199001011234，邮箱 alice@example.com"
  }'
```

**响应示例：**

```json
{
  "document_id": null,
  "findings": [
    {
      "type": "pii",
      "label": "phone",
      "matched_text": "13800138000",
      "start": 5,
      "end": 16,
      "severity": "L2",
      "confidence": 1.0,
      "metadata": {},
      "doc_id": null,
      "chunk_index": null
    },
    {
      "type": "pii",
      "label": "id_card",
      "matched_text": "110101199001011234",
      "start": 23,
      "end": 41,
      "severity": "L3",
      "confidence": 1.0,
      "metadata": {},
      "doc_id": null,
      "chunk_index": null
    }
  ],
  "masked_text": "请联系我 [PHONE]，身份证号 [IDCARD]，邮箱 [EMAIL]",
  "summary": {
    "total": 3,
    "by_type": { "pii": 3 },
    "by_label": { "phone": 1, "id_card": 1, "email": 1 }
  }
}
```

### 9.2 扫描已上传文档的所有 Chunk

```bash
curl -X POST "http://localhost:8000/api/v1/keywords/scan/" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "66666666-7777-8888-9999-000000000000"
  }'
```

**响应示例：**

```json
{
  "document_id": "66666666-7777-8888-9999-000000000000",
  "findings": [
    {
      "type": "keyword",
      "label": "confidential",
      "matched_text": "机密",
      "start": 12,
      "end": 14,
      "severity": "L3",
      "confidence": 1.0,
      "metadata": { "keyword_id": "...", "keyword": "机密", "action": "audit" },
      "doc_id": "66666666-7777-8888-9999-000000000000",
      "chunk_index": 2
    }
  ],
  "summary": {
    "total": 1,
    "chunks_scanned": 8,
    "chunks_with_findings": 1,
    "by_type": { "keyword": 1 },
    "by_label": { "confidential": 1 }
  }
}
```

---

## 附录：常用响应状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 删除成功，无返回体 |
| 400 | 请求参数错误 |
| 401 | 未授权，Token 缺失或过期 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 422 | 请求体校验失败 |
| 503 | 服务暂不可用（如 Celery 任务派发失败） |

---

## 附录：前端对接提示

- 前端 axios 基址已配置为 `/api`，并通过请求拦截器自动注入 `Authorization: Bearer <token>`，详见 `frontend/src/services/api.ts`。
- 流式接口建议在前端使用 `@microsoft/fetch-event-source` 或 `fetch` + `ReadableStream` 解析 SSE，以便携带 Token 与自定义请求体。
