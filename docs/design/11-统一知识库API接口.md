# 11 - 统一知识库 API 接口设计

> 版本: v1.0 | 日期: 2026-06-10 | 状态: 方案设计阶段
> 后端框架: FastAPI | API 规范: OpenAPI 3.0 | 传输协议: RESTful + SSE

---

## 目录

1. [设计原则与约定](#1-设计原则与约定)
2. [统一响应格式](#2-统一响应格式)
3. [API 版本控制策略](#3-api-版本控制策略)
4. [认证与请求头](#4-认证与请求头)
5. [知识库管理 API](#5-知识库管理-api)
6. [文档管理 API](#6-文档管理-api)
7. [检索 API](#7-检索-api)
8. [问答 API](#8-问答-api)
9. [权限管理 API](#9-权限管理-api)
10. [评测 API](#10-评测-api)
11. [关键词管理 API](#11-关键词管理-api)
12. [用户群管理 API](#12-用户群管理-api)
13. [统一错误码定义表](#13-统一错误码定义表)
14. [Python SDK 示例](#14-python-sdk-示例)
15. [JavaScript SDK 示例](#15-javascript-sdk-示例)
16. [OpenAPI 3.0 片段](#16-openapi-30-片段)

---

## 1. 设计原则与约定

### 1.1 核心原则

| 原则 | 说明 |
|------|------|
| **统一信封** | 所有接口返回统一结构 `{code, message, data, request_id}`，业务数据一律放在 `data` 中 |
| **RESTful 路径** | 资源名使用复数 kebab-case，操作通过 HTTP Method 表达 |
| **流式标准化** | SSE 流仅用于 `/chat/completions`，事件类型固定为 `message` / `done` / `error` |
| **权限穿透** | 所有数据操作接口自动携带 `X-User-Context` 上下文，服务端完成五级权限校验 |
| **幂等设计** | 创建类接口支持 `Idempotency-Key`，防止重复提交 |
| **分页统一** | 列表接口统一返回 `{items, total, page, page_size, has_more}` |

### 1.2 请求头规范

```
Authorization: Bearer <JWT-Token>
Content-Type: application/json
X-Request-ID: <UUID>              # 客户端生成，全链路追踪
X-User-Context: <base64_json>     # 可选，网关自动注入
Idempotency-Key: <UUID>           # 可选，幂等键（30分钟有效期）
Accept: application/json          # 常规请求
Accept: text/event-stream         # SSE 流式请求
```

### 1.3 Base64 用户上下文格式

```json
{
  "user_id": "u_123456",
  "group_ids": ["g_001", "g_003"],
  "security_level": "L2",
  "client_ip": "10.0.1.55"
}
```

---

## 2. 统一响应格式

### 2.1 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": { ... },
  "request_id": "req_7f8a9b2c3d4e"
}
```

### 2.2 错误响应

```json
{
  "code": 40001,
  "message": "知识库名称不能为空",
  "data": null,
  "request_id": "req_7f8a9b2c3d4e"
}
```

### 2.3 列表分页响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [ ... ],
    "total": 128,
    "page": 1,
    "page_size": 20,
    "has_more": true
  },
  "request_id": "req_7f8a9b2c3d4e"
}
```

---

## 3. API 版本控制策略

### 3.1 版本策略总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                        API 版本控制策略                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   URL 路径版本 (主版本)                                               │
│   ├── /api/v1/...          ← 当前主版本                               │
│   └── /api/v2/...          ← 未来主版本（不兼容变更时启用）              │
│                                                                      │
│   请求头微调版本 (子版本)                                              │
│   └── X-API-Version: 2024-06-01    ← 功能迭代，向后兼容               │
│                                                                      │
│   弃用策略                                                            │
│   ├── 弃用通知: Response Header 返回 Deprecation: true                │
│   ├── 兼容期: 至少保留 6 个月                                         │
│   └── 文档标注: OpenAPI 中标记 deprecated: true                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 版本协商规则

| 场景 | 处理方式 |
|------|----------|
| 客户端未带 `X-API-Version` | 使用最新稳定子版本 |
| 子版本不存在 | 返回 `40009` 错误，提示可用版本列表 |
| 主版本已下线 | 返回 `410 Gone`，响应体中包含迁移指南 |

---

## 4. 认证与请求头

### 4.1 JWT Token 结构

```json
{
  "sub": "u_123456",
  "groups": ["g_001", "g_003"],
  "role": "admin",
  "iat": 1718000000,
  "exp": 1718604800,
  "jti": "tkn_a1b2c3d4"
}
```

### 4.2 认证失败响应

```json
{
  "code": 40101,
  "message": "Token 已过期或无效",
  "data": null,
  "request_id": "req_9f8e7d6c5b4a"
}
```

---

## 5. 知识库管理 API

### 5.1 创建知识库

```yaml
Method: POST
Path:   /api/v1/knowledge-bases
Tags:   [知识库管理]
```

**Request Body:**

```json
{
  "name": "产品研发知识库",
  "description": "包含产品需求文档、技术方案、API文档等",
  "embedding_model": "bge-m3",
  "chunk_size": 512,
  "chunk_overlap": 50,
  "rerank_model": "bge-reranker-base",
  "metadata": {
    "department": "研发部",
    "owner": "u_123456"
  },
  "default_security_level": "L2"
}
```

**Response 201:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "kb_7a8b9c0d1e2f",
    "name": "产品研发知识库",
    "description": "包含产品需求文档、技术方案、API文档等",
    "status": "active",
    "embedding_model": "bge-m3",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "rerank_model": "bge-reranker-base",
    "document_count": 0,
    "total_chunks": 0,
    "storage_used_bytes": 0,
    "metadata": {
      "department": "研发部",
      "owner": "u_123456"
    },
    "default_security_level": "L2",
    "created_at": "2026-06-10T06:30:00Z",
    "updated_at": "2026-06-10T06:30:00Z",
    "created_by": "u_123456"
  },
  "request_id": "req_1a2b3c4d5e6f"
}
```

### 5.2 获取知识库列表

```yaml
Method: GET
Path:   /api/v1/knowledge-bases
Tags:   [知识库管理]
```

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，最大 100 |
| `search` | string | 否 | 按名称模糊搜索 |
| `status` | string | 否 | 筛选状态：`active` / `frozen` / `archived` |
| `sort_by` | string | 否 | 排序字段，默认 `updated_at` |
| `sort_order` | string | 否 | `asc` / `desc`，默认 `desc` |

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "kb_7a8b9c0d1e2f",
        "name": "产品研发知识库",
        "description": "包含产品需求文档、技术方案、API文档等",
        "status": "active",
        "document_count": 42,
        "total_chunks": 3580,
        "storage_used_bytes": 268435456,
        "created_at": "2026-06-10T06:30:00Z",
        "updated_at": "2026-06-10T08:15:00Z",
        "created_by": "u_123456"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20,
    "has_more": false
  },
  "request_id": "req_2b3c4d5e6f7g"
}
```

### 5.3 获取知识库详情

```yaml
Method: GET
Path:   /api/v1/knowledge-bases/{kb_id}
Tags:   [知识库管理]
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "kb_7a8b9c0d1e2f",
    "name": "产品研发知识库",
    "description": "包含产品需求文档、技术方案、API文档等",
    "status": "active",
    "embedding_model": "bge-m3",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "rerank_model": "bge-reranker-base",
    "document_count": 42,
    "total_chunks": 3580,
    "storage_used_bytes": 268435456,
    "metadata": {
      "department": "研发部",
      "owner": "u_123456"
    },
    "default_security_level": "L2",
    "created_at": "2026-06-10T06:30:00Z",
    "updated_at": "2026-06-10T08:15:00Z",
    "created_by": "u_123456"
  },
  "request_id": "req_3c4d5e6f7g8h"
}
```

### 5.4 更新知识库

```yaml
Method: PUT
Path:   /api/v1/knowledge-bases/{kb_id}
Tags:   [知识库管理]
```

**Request Body:**

```json
{
  "name": "产品研发知识库 V2",
  "description": "更新后的描述",
  "rerank_model": "bge-reranker-large",
  "metadata": {
    "department": "研发部",
    "owner": "u_123456",
    "reviewer": "u_789012"
  },
  "default_security_level": "L2"
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "kb_7a8b9c0d1e2f",
    "name": "产品研发知识库 V2",
    "description": "更新后的描述",
    "status": "active",
    "rerank_model": "bge-reranker-large",
    "updated_at": "2026-06-10T09:00:00Z"
  },
  "request_id": "req_4d5e6f7g8h9i"
}
```

### 5.5 删除知识库

```yaml
Method: DELETE
Path:   /api/v1/knowledge-bases/{kb_id}
Tags:   [知识库管理]
Query:  ?force=false   # force=true 时物理删除，否则逻辑删除
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "kb_7a8b9c0d1e2f",
    "deleted_at": "2026-06-10T09:30:00Z",
    "force_deleted": false
  },
  "request_id": "req_5e6f7g8h9i0j"
}
```

---

## 6. 文档管理 API

### 6.1 上传文档

```yaml
Method: POST
Path:   /api/v1/knowledge-bases/{kb_id}/documents
Tags:   [文档管理]
Content-Type: multipart/form-data
```

**Request Body (multipart):**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `files` | File[] | 是 | 支持批量上传，单文件最大 500MB |
| `security_level` | string | 否 | `L0`-`L4`，默认继承知识库配置 |
| `tags` | string[] | 否 | 文档标签 ID 列表 |
| `metadata` | JSON string | 否 | 自定义元数据 |
| `parse_options` | JSON string | 否 | 解析选项，覆盖知识库默认配置 |

**Parse Options 示例:**

```json
{
  "chunk_size": 1024,
  "chunk_overlap": 100,
  "extract_tables": true,
  "ocr_enabled": true,
  "language": "zh"
}
```

**Response 202 (Accepted):**

```json
{
  "code": 0,
  "message": "文档已接收，正在异步处理中",
  "data": {
    "task_id": "task_a1b2c3d4e5f6",
    "documents": [
      {
        "id": "doc_1a2b3c4d5e6f",
        "filename": "产品需求文档_v3.pdf",
        "status": "pending",
        "size_bytes": 12582912,
        "mime_type": "application/pdf"
      }
    ],
    "estimated_seconds": 45
  },
  "request_id": "req_6f7g8h9i0j1k"
}
```

### 6.2 链接摄取

```yaml
Method: POST
Path:   /api/v1/knowledge-bases/{kb_id}/documents/link
Tags:   [文档管理]
```

**Request Body:**

```json
{
  "url": "https://confluence.company.com/pages/viewpage.action?pageId=12345",
  "title": "Confluence 技术方案页",
  "security_level": "L2",
  "tags": ["tag_001", "tag_003"],
  "metadata": {
    "source_type": "confluence",
    "space_key": "TECH"
  },
  "parse_options": {
    "extract_attachments": true,
    "max_depth": 1
  }
}
```

**Response 202:**

```json
{
  "code": 0,
  "message": "链接已接收，正在异步抓取中",
  "data": {
    "task_id": "task_b2c3d4e5f6g7",
    "document_id": "doc_2b3c4d5e6f7g",
    "status": "pending",
    "url": "https://confluence.company.com/pages/viewpage.action?pageId=12345"
  },
  "request_id": "req_7g8h9i0j1k2l"
}
```

### 6.3 获取文档列表

```yaml
Method: GET
Path:   /api/v1/knowledge-bases/{kb_id}/documents
Tags:   [文档管理]
```

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20，最大 100 |
| `status` | string | 否 | `pending` / `parsing` / `indexed` / `failed` |
| `search` | string | 否 | 按文件名搜索 |
| `tag_ids` | string | 否 | 逗号分隔的标签 ID 筛选 |

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "doc_1a2b3c4d5e6f",
        "filename": "产品需求文档_v3.pdf",
        "status": "indexed",
        "size_bytes": 12582912,
        "mime_type": "application/pdf",
        "chunk_count": 86,
        "security_level": "L2",
        "tags": [
          { "id": "tag_001", "name": "产品", "color": "#1890ff" }
        ],
        "metadata": {
          "author": "张三",
          "pages": 24
        },
        "created_at": "2026-06-10T07:00:00Z",
        "updated_at": "2026-06-10T07:05:00Z",
        "indexed_at": "2026-06-10T07:05:00Z"
      }
    ],
    "total": 42,
    "page": 1,
    "page_size": 20,
    "has_more": true
  },
  "request_id": "req_8h9i0j1k2l3m"
}
```

### 6.4 获取文档详情

```yaml
Method: GET
Path:   /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}
Tags:   [文档管理]
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "doc_1a2b3c4d5e6f",
    "kb_id": "kb_7a8b9c0d1e2f",
    "filename": "产品需求文档_v3.pdf",
    "status": "indexed",
    "size_bytes": 12582912,
    "mime_type": "application/pdf",
    "chunk_count": 86,
    "security_level": "L2",
    "tags": [
      { "id": "tag_001", "name": "产品", "color": "#1890ff" }
    ],
    "metadata": {
      "author": "张三",
      "pages": 24
    },
    "parse_result": {
      "title": "产品需求文档 V3",
      "language": "zh",
      "extracted_tables": 3,
      "extracted_images": 12
    },
    "chunks_preview": [
      {
        "id": "chunk_001",
        "index": 0,
        "text_preview": "1. 产品概述 本产品旨在...",
        "token_count": 256
      }
    ],
    "created_at": "2026-06-10T07:00:00Z",
    "updated_at": "2026-06-10T07:05:00Z",
    "indexed_at": "2026-06-10T07:05:00Z"
  },
  "request_id": "req_9i0j1k2l3m4n"
}
```

### 6.5 删除文档

```yaml
Method: DELETE
Path:   /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}
Tags:   [文档管理]
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "doc_1a2b3c4d5e6f",
    "deleted_at": "2026-06-10T10:00:00Z",
    "vectors_removed": 86,
    "storage_freed_bytes": 12582912
  },
  "request_id": "req_0j1k2l3m4n5o"
}
```

### 6.6 重新索引文档

```yaml
Method: POST
Path:   /api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/reindex
Tags:   [文档管理]
```

**Request Body:**

```json
{
  "parse_options": {
    "chunk_size": 1024,
    "chunk_overlap": 100,
    "ocr_enabled": true,
    "embedding_model": "bge-m3"
  },
  "reason": "更换分块策略"
}
```

**Response 202:**

```json
{
  "code": 0,
  "message": "重新索引任务已提交",
  "data": {
    "task_id": "task_c3d4e5f6g7h8",
    "document_id": "doc_1a2b3c4d5e6f",
    "status": "pending",
    "estimated_seconds": 60
  },
  "request_id": "req_1k2l3m4n5o6p"
}
```

---

## 7. 检索 API

### 7.1 统一检索

```yaml
Method: POST
Path:   /api/v1/search
Tags:   [检索引擎]
```

**Request Body:**

```json
{
  "query": "如何配置负载均衡？",
  "kb_ids": ["kb_7a8b9c0d1e2f"],
  "search_type": "hybrid",
  "top_k": 10,
  "filters": {
    "doc_ids": ["doc_1a2b3c4d5e6f"],
    "security_levels": ["L1", "L2"],
    "tags": ["tag_001"],
    "mime_types": ["application/pdf", "text/markdown"],
    "created_after": "2026-01-01T00:00:00Z",
    "created_before": "2026-12-31T23:59:59Z"
  },
  "rerank": {
    "enabled": true,
    "model": "bge-reranker-large",
    "top_n": 5
  },
  "highlight": {
    "enabled": true,
    "pre_tag": "<mark>",
    "post_tag": "</mark>"
  },
  "return_chunks": true,
  "return_metadata": true
}
```

**字段说明:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 检索查询文本，支持自然语言 |
| `kb_ids` | string[] | 是 | 目标知识库 ID 列表，最多 10 个 |
| `search_type` | string | 否 | `dense` / `sparse` / `hybrid` / `image`，默认 `hybrid` |
| `top_k` | int | 否 | 返回结果数，默认 10，最大 100 |
| `filters` | object | 否 | 多维过滤条件 |
| `rerank` | object | 否 | 重排序配置 |
| `highlight` | object | 否 | 高亮配置 |
| `return_chunks` | bool | 否 | 是否返回完整 chunk 内容，默认 true |
| `return_metadata` | bool | 否 | 是否返回文档元数据，默认 true |

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "query": "如何配置负载均衡？",
    "total_hits": 156,
    "retrieval_time_ms": 45,
    "rerank_time_ms": 23,
    "permission_filter_time_ms": 8,
    "results": [
      {
        "rank": 1,
        "score": 0.9234,
        "rerank_score": 0.9567,
        "chunk": {
          "id": "chunk_00a1b2c3",
          "doc_id": "doc_1a2b3c4d5e6f",
          "kb_id": "kb_7a8b9c0d1e2f",
          "index": 15,
          "text": "在 Nginx 中配置负载均衡，首先需要编辑 nginx.conf 文件，在 http 块中添加 upstream 指令...",
          "text_highlighted": "在 Nginx 中配置<mark>负载均衡</mark>，首先需要编辑 nginx.conf 文件...",
          "token_count": 312,
          "security_level": "L2",
          "metadata": {
            "page": 8,
            "section": "部署指南"
          }
        },
        "document": {
          "id": "doc_1a2b3c4d5e6f",
          "filename": "部署手册_v2.pdf",
          "mime_type": "application/pdf",
          "tags": [{ "id": "tag_001", "name": "运维" }]
        }
      }
    ],
    "search_params": {
      "search_type": "hybrid",
      "top_k": 10,
      "rerank_model": "bge-reranker-large",
      "filtered_kb_ids": ["kb_7a8b9c0d1e2f"]
    }
  },
  "request_id": "req_2l3m4n5o6p7q"
}
```

### 7.2 以图搜图

```yaml
Method: POST
Path:   /api/v1/search/image
Tags:   [检索引擎]
Content-Type: multipart/form-data
```

**Request Body (multipart):**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image` | File | 是 | 查询图片，支持 jpg/png/webp，最大 10MB |
| `kb_ids` | string | 是 | 逗号分隔的知识库 ID |
| `top_k` | int | 否 | 默认 10 |
| `filters` | JSON string | 否 | 同统一检索 filters |

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "results": [
      {
        "rank": 1,
        "score": 0.8912,
        "chunk": {
          "id": "chunk_img_001",
          "doc_id": "doc_3c4d5e6f7g8h",
          "image_url": "/api/v1/knowledge-bases/kb_xxx/documents/doc_xxx/images/img_001.jpg",
          "description": "系统架构图：展示微服务部署拓扑"
        },
        "document": {
          "id": "doc_3c4d5e6f7g8h",
          "filename": "架构设计文档.pdf"
        }
      }
    ]
  },
  "request_id": "req_3m4n5o6p7q8r"
}
```

---

## 8. 问答 API

### 8.1 非流式问答

```yaml
Method: POST
Path:   /api/v1/chat/completions
Tags:   [问答引擎]
```

**Request Body:**

```json
{
  "model": "rag-default",
  "messages": [
    { "role": "system", "content": "你是一个企业知识库助手，基于检索到的上下文回答问题。" },
    { "role": "user", "content": "如何配置负载均衡？" }
  ],
  "kb_ids": ["kb_7a8b9c0d1e2f"],
  "stream": false,
  "temperature": 0.3,
  "max_tokens": 2048,
  "search_params": {
    "top_k": 10,
    "rerank": {
      "enabled": true,
      "top_n": 5
    },
    "filters": {
      "security_levels": ["L1", "L2"]
    }
  },
  "context_compression": {
    "enabled": true,
    "max_context_tokens": 4000,
    "strategy": "hierarchical"
  },
  "citation": {
    "enabled": true,
    "format": "markdown"
  }
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "chat_4n5o6p7q8r9s",
    "model": "rag-default",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "根据检索到的文档，配置负载均衡的步骤如下：\n\n1. 编辑 nginx.conf 文件...\n\n[参考文档: 部署手册_v2.pdf 第8页]"
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 1523,
      "completion_tokens": 256,
      "total_tokens": 1779
    },
    "retrieval_info": {
      "query": "如何配置负载均衡？",
      "retrieved_chunks": 5,
      "retrieval_time_ms": 68,
      "citations": [
        {
          "chunk_id": "chunk_00a1b2c3",
          "doc_id": "doc_1a2b3c4d5e6f",
          "doc_name": "部署手册_v2.pdf",
          "page": 8,
          "relevance_score": 0.9567
        }
      ]
    },
    "created": 1718010000
  },
  "request_id": "req_4n5o6p7q8r9s"
}
```

### 8.2 SSE 流式问答

```yaml
Method: POST
Path:   /api/v1/chat/completions
Tags:   [问答引擎]
Headers:
  Accept: text/event-stream
```

**Request Body:**

```json
{
  "model": "rag-default",
  "messages": [
    { "role": "user", "content": "如何配置负载均衡？" }
  ],
  "kb_ids": ["kb_7a8b9c0d1e2f"],
  "stream": true,
  "temperature": 0.3,
  "search_params": {
    "top_k": 10,
    "rerank": { "enabled": true, "top_n": 5 }
  },
  "citation": { "enabled": true, "format": "markdown" }
}
```

**SSE 流输出:**

```text
event: message
data: {"id":"chat_5o6p7q8r9s0t","object":"chat.completion.chunk","created":1718010001,"model":"rag-default","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

event: message
data: {"id":"chat_5o6p7q8r9s0t","object":"chat.completion.chunk","created":1718010001,"model":"rag-default","choices":[{"index":0,"delta":{"content":"根据"},"finish_reason":null}]}

event: message
data: {"id":"chat_5o6p7q8r9s0t","object":"chat.completion.chunk","created":1718010002,"model":"rag-default","choices":[{"index":0,"delta":{"content":"检索到的文档"},"finish_reason":null}]}

event: message
data: {"id":"chat_5o6p7q8r9s0t","object":"chat.completion.chunk","created":1718010003,"model":"rag-default","choices":[{"index":0,"delta":{"content":"，配置负载均衡的步骤如下：\n\n1. 编辑 nginx.conf..."},"finish_reason":null}]}

event: message
data: {"id":"chat_5o6p7q8r9s0t","object":"chat.completion.chunk","created":1718010005,"model":"rag-default","choices":[{"index":0,"delta":{},"finish_reason":"stop","citations":[{"chunk_id":"chunk_00a1b2c3","doc_name":"部署手册_v2.pdf","page":8}]}]}

event: done
data: {"usage":{"prompt_tokens":1523,"completion_tokens":256,"total_tokens":1779},"retrieval_time_ms":68}

```

**SSE 事件类型说明:**

| 事件类型 | 说明 |
|----------|------|
| `message` | 标准内容块，对应 `delta` 增量数据 |
| `retrieval` | 检索完成事件（可选），携带召回上下文摘要 |
| `done` | 流结束事件，携带 `usage` 统计信息 |
| `error` | 流过程中发生错误，携带错误码和消息 |

**SSE Error 示例:**

```text
event: error
data: {"code":40301,"message":"无权访问目标知识库","request_id":"req_6p7q8r9s0t1u"}

```

---

## 9. 权限管理 API

### 9.1 文档级别权限配置

```yaml
Method: POST
Path:   /api/v1/permissions/documents
Tags:   [权限管理]
```

**Request Body:**

```json
{
  "doc_id": "doc_1a2b3c4d5e6f",
  "rules": [
    {
      "group_id": "g_001",
      "action": "read",
      "effect": "allow"
    },
    {
      "group_id": "g_002",
      "action": "read",
      "effect": "deny"
    }
  ],
  "inherit_from_kb": false
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "doc_id": "doc_1a2b3c4d5e6f",
    "applied_rules": 2,
    "effective_groups": ["g_001"],
    "denied_groups": ["g_002"],
    "updated_at": "2026-06-10T11:00:00Z"
  },
  "request_id": "req_7q8r9s0t1u2v"
}
```

### 9.2 字段级别权限配置

```yaml
Method: POST
Path:   /api/v1/permissions/fields
Tags:   [权限管理]
```

**Request Body:**

```json
{
  "doc_id": "doc_1a2b3c4d5e6f",
  "rules": [
    {
      "group_id": "g_001",
      "field_pattern": "salary",
      "action": "read",
      "effect": "deny"
    },
    {
      "group_id": "g_001",
      "field_pattern": "name|department",
      "action": "read",
      "effect": "allow"
    }
  ]
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "doc_id": "doc_1a2b3c4d5e6f",
    "field_rules_count": 2,
    "updated_at": "2026-06-10T11:05:00Z"
  },
  "request_id": "req_8r9s0t1u2v3w"
}
```

### 9.3 标签级别权限配置

```yaml
Method: POST
Path:   /api/v1/permissions/tags
Tags:   [权限管理]
```

**Request Body:**

```json
{
  "tag_id": "tag_003",
  "rules": [
    {
      "group_id": "g_001",
      "action": "read",
      "effect": "allow"
    },
    {
      "group_id": "g_002",
      "action": "read",
      "effect": "deny"
    }
  ]
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "tag_id": "tag_003",
    "tag_name": "机密",
    "allowed_groups": ["g_001"],
    "denied_groups": ["g_002"],
    "updated_at": "2026-06-10T11:10:00Z"
  },
  "request_id": "req_9s0t1u2v3w4x"
}
```

### 9.4 群级别权限配置（RBAC）

```yaml
Method: POST
Path:   /api/v1/permissions/groups
Tags:   [权限管理]
```

**Request Body:**

```json
{
  "group_id": "g_001",
  "kb_permissions": [
    {
      "kb_id": "kb_7a8b9c0d1e2f",
      "actions": ["read", "search", "chat"],
      "effect": "allow"
    }
  ],
  "file_type_permissions": [
    {
      "mime_types": ["application/pdf", "text/markdown"],
      "action": "read",
      "effect": "allow"
    },
    {
      "mime_types": ["video/mp4"],
      "action": "read",
      "effect": "deny"
    }
  ],
  "security_level_ceiling": "L3"
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "group_id": "g_001",
    "group_name": "研发团队",
    "effective_kb_ids": ["kb_7a8b9c0d1e2f"],
    "security_level_ceiling": "L3",
    "updated_at": "2026-06-10T11:15:00Z"
  },
  "request_id": "req_0t1u2v3w4x5y"
}
```

### 9.5 权限校验（调试）

```yaml
Method: POST
Path:   /api/v1/permissions/check
Tags:   [权限管理]
```

**Request Body:**

```json
{
  "user_id": "u_123456",
  "resource_type": "document",
  "resource_id": "doc_1a2b3c4d5e6f",
  "action": "read"
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "allowed": true,
    "decision": "allow",
    "reason": "用户所在群 g_001 拥有文档读取权限",
    "applied_levels": ["group_permission", "document_permission"],
    "latency_ms": 3
  },
  "request_id": "req_1u2v3w4x5y6z"
}
```

---

## 10. 评测 API

### 10.1 提交评测任务

```yaml
Method: POST
Path:   /api/v1/evaluation/tasks
Tags:   [评测系统]
```

**Request Body:**

```json
{
  "name": "Q1 检索质量评测",
  "kb_id": "kb_7a8b9c0d1e2f",
  "dataset": {
    "source_type": "upload",
    "qa_pairs": [
      {
        "question": "如何配置负载均衡？",
        "ground_truth": "在 Nginx 中配置 upstream 指令...",
        "expected_doc_ids": ["doc_1a2b3c4d5e6f"]
      }
    ]
  },
  "metrics": ["recall@k", "precision@k", "mrr", "ndcg"],
  "search_config": {
    "top_k": 10,
    "rerank": { "enabled": true, "top_n": 5 },
    "search_type": "hybrid"
  },
  "notify_webhook": "https://company.com/webhooks/eval-complete"
}
```

**Response 202:**

```json
{
  "code": 0,
  "message": "评测任务已提交",
  "data": {
    "task_id": "eval_2v3w4x5y6z7a",
    "name": "Q1 检索质量评测",
    "status": "queued",
    "estimated_seconds": 300,
    "queued_at": "2026-06-10T12:00:00Z"
  },
  "request_id": "req_2v3w4x5y6z7a"
}
```

### 10.2 获取评测结果

```yaml
Method: GET
Path:   /api/v1/evaluation/tasks/{task_id}
Tags:   [评测系统]
```

**Response 200 (运行中):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "eval_2v3w4x5y6z7a",
    "name": "Q1 检索质量评测",
    "status": "running",
    "progress": {
      "total": 100,
      "completed": 45,
      "failed": 0
    },
    "started_at": "2026-06-10T12:01:00Z"
  },
  "request_id": "req_3w4x5y6z7a8b"
}
```

**Response 200 (已完成):**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "eval_2v3w4x5y6z7a",
    "name": "Q1 检索质量评测",
    "status": "completed",
    "progress": { "total": 100, "completed": 100, "failed": 0 },
    "started_at": "2026-06-10T12:01:00Z",
    "completed_at": "2026-06-10T12:06:00Z",
    "summary": {
      "recall_at_5": 0.82,
      "recall_at_10": 0.91,
      "precision_at_5": 0.76,
      "mrr": 0.84,
      "ndcg_at_10": 0.88,
      "average_latency_ms": 52
    },
    "per_question": [
      {
        "question": "如何配置负载均衡？",
        "recall_at_5": 1.0,
        "retrieved_docs": ["doc_1a2b3c4d5e6f"],
        "latency_ms": 45
      }
    ]
  },
  "request_id": "req_4x5y6z7a8b9c"
}
```

### 10.3 对比评测

```yaml
Method: POST
Path:   /api/v1/evaluation/compare
Tags:   [评测系统]
```

**Request Body:**

```json
{
  "name": "重排序模型对比实验",
  "kb_id": "kb_7a8b9c0d1e2f",
  "dataset_id": "ds_001",
  "configs": [
    {
      "name": "基线-无重排",
      "search_config": {
        "search_type": "hybrid",
        "top_k": 10,
        "rerank": { "enabled": false }
      }
    },
    {
      "name": "bge-reranker-base",
      "search_config": {
        "search_type": "hybrid",
        "top_k": 10,
        "rerank": { "enabled": true, "model": "bge-reranker-base", "top_n": 5 }
      }
    },
    {
      "name": "bge-reranker-large",
      "search_config": {
        "search_type": "hybrid",
        "top_k": 10,
        "rerank": { "enabled": true, "model": "bge-reranker-large", "top_n": 5 }
      }
    }
  ],
  "metrics": ["recall@k", "mrr", "ndcg"]
}
```

**Response 202:**

```json
{
  "code": 0,
  "message": "对比评测任务已提交",
  "data": {
    "task_id": "eval_cmp_5y6z7a8b9c0d",
    "config_count": 3,
    "status": "queued"
  },
  "request_id": "req_5y6z7a8b9c0d"
}
```

---

## 11. 关键词管理 API

### 11.1 获取敏感关键词配置

```yaml
Method: GET
Path:   /api/v1/keywords
Tags:   [关键词管理]
```

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `level` | string | 否 | `L1`-`L4` 筛选 |
| `category` | string | 否 | 分类筛选：`compliance` / `security` / `privacy` |
| `enabled` | bool | 否 | 是否启用筛选 |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 50 |

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "kw_001",
        "word": "并购",
        "level": "L4",
        "category": "security",
        "match_mode": "exact",
        "action": "block",
        "description": "涉及商业机密，L3及以下用户不可见",
        "enabled": true,
        "created_at": "2026-01-15T00:00:00Z",
        "updated_at": "2026-06-01T00:00:00Z"
      },
      {
        "id": "kw_002",
        "word": "身份证号",
        "level": "L3",
        "category": "privacy",
        "match_mode": "regex",
        "pattern": "\\d{17}[\\dXx]",
        "action": "mask",
        "replacement": "***************",
        "description": "个人隐私信息自动脱敏",
        "enabled": true,
        "created_at": "2026-02-20T00:00:00Z"
      }
    ],
    "total": 128,
    "page": 1,
    "page_size": 50,
    "has_more": true
  },
  "request_id": "req_6z7a8b9c0d1e"
}
```

### 11.2 创建敏感关键词

```yaml
Method: POST
Path:   /api/v1/keywords
Tags:   [关键词管理]
```

**Request Body:**

```json
{
  "word": "核心算法参数",
  "level": "L4",
  "category": "security",
  "match_mode": "exact",
  "action": "block",
  "description": "核心技术参数禁止外泄"
}
```

**Response 201:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "kw_003",
    "word": "核心算法参数",
    "level": "L4",
    "category": "security",
    "match_mode": "exact",
    "action": "block",
    "enabled": true,
    "created_at": "2026-06-10T13:00:00Z"
  },
  "request_id": "req_7a8b9c0d1e2f"
}
```

### 11.3 更新敏感关键词

```yaml
Method: PUT
Path:   /api/v1/keywords/{keyword_id}
Tags:   [关键词管理]
```

**Request Body:**

```json
{
  "level": "L3",
  "action": "mask",
  "replacement": "[已脱敏]",
  "enabled": true,
  "description": "调整为脱敏处理，非完全阻断"
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "kw_003",
    "word": "核心算法参数",
    "level": "L3",
    "action": "mask",
    "enabled": true,
    "updated_at": "2026-06-10T13:30:00Z"
  },
  "request_id": "req_8b9c0d1e2f3g"
}
```

### 11.4 删除敏感关键词

```yaml
Method: DELETE
Path:   /api/v1/keywords/{keyword_id}
Tags:   [关键词管理]
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "kw_003",
    "deleted_at": "2026-06-10T14:00:00Z"
  },
  "request_id": "req_9c0d1e2f3g4h"
}
```

### 11.5 批量导入关键词

```yaml
Method: POST
Path:   /api/v1/keywords/batch
Tags:   [关键词管理]
Content-Type: multipart/form-data
```

**Request Body (multipart):**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | CSV/Excel 文件，列：word, level, category, match_mode, action |
| `overwrite` | bool | 否 | 是否覆盖已有同关键词，默认 false |

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 50,
    "imported": 48,
    "skipped": 2,
    "errors": [
      { "row": 12, "word": "并购", "reason": "关键词已存在且 overwrite=false" }
    ]
  },
  "request_id": "req_0d1e2f3g4h5i"
}
```

---

## 12. 用户群管理 API

### 12.1 获取用户群列表

```yaml
Method: GET
Path:   /api/v1/user-groups
Tags:   [用户群管理]
```

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20 |
| `search` | string | 否 | 按群名称搜索 |
| `status` | string | 否 | `active` / `inactive` |

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "g_001",
        "name": "研发团队",
        "description": "全体研发人员",
        "member_count": 56,
        "security_level_ceiling": "L3",
        "status": "active",
        "created_at": "2026-01-10T00:00:00Z",
        "updated_at": "2026-06-01T00:00:00Z"
      },
      {
        "id": "g_002",
        "name": "管理层",
        "description": "部门经理及以上",
        "member_count": 12,
        "security_level_ceiling": "L4",
        "status": "active",
        "created_at": "2026-01-10T00:00:00Z"
      }
    ],
    "total": 8,
    "page": 1,
    "page_size": 20,
    "has_more": false
  },
  "request_id": "req_1e2f3g4h5i6j"
}
```

### 12.2 创建用户群

```yaml
Method: POST
Path:   /api/v1/user-groups
Tags:   [用户群管理]
```

**Request Body:**

```json
{
  "name": "安全合规组",
  "description": "负责安全合规审查的人员",
  "security_level_ceiling": "L4",
  "initial_member_ids": ["u_123456", "u_789012"],
  "metadata": {
    "department": "安全部",
    "cost_center": "CC-009"
  }
}
```

**Response 201:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "g_003",
    "name": "安全合规组",
    "description": "负责安全合规审查的人员",
    "security_level_ceiling": "L4",
    "member_count": 2,
    "status": "active",
    "metadata": {
      "department": "安全部",
      "cost_center": "CC-009"
    },
    "created_at": "2026-06-10T14:30:00Z"
  },
  "request_id": "req_2f3g4h5i6j7k"
}
```

### 12.3 更新用户群

```yaml
Method: PUT
Path:   /api/v1/user-groups/{group_id}
Tags:   [用户群管理]
```

**Request Body:**

```json
{
  "name": "安全合规组（更新）",
  "description": "更新后的描述",
  "security_level_ceiling": "L4",
  "status": "active"
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "g_003",
    "name": "安全合规组（更新）",
    "security_level_ceiling": "L4",
    "updated_at": "2026-06-10T15:00:00Z"
  },
  "request_id": "req_3g4h5i6j7k8l"
}
```

### 12.4 删除用户群

```yaml
Method: DELETE
Path:   /api/v1/user-groups/{group_id}
Tags:   [用户群管理]
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "g_003",
    "deleted_at": "2026-06-10T15:30:00Z",
    "members_removed": 2
  },
  "request_id": "req_4h5i6j7k8l9m"
}
```

### 12.5 获取群成员列表

```yaml
Method: GET
Path:   /api/v1/user-groups/{group_id}/members
Tags:   [用户群管理]
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "group_id": "g_001",
    "group_name": "研发团队",
    "items": [
      {
        "user_id": "u_123456",
        "username": "zhangsan",
        "display_name": "张三",
        "email": "zhangsan@company.com",
        "role_in_group": "member",
        "joined_at": "2026-01-15T00:00:00Z"
      },
      {
        "user_id": "u_789012",
        "username": "lisi",
        "display_name": "李四",
        "email": "lisi@company.com",
        "role_in_group": "admin",
        "joined_at": "2026-01-10T00:00:00Z"
      }
    ],
    "total": 56,
    "page": 1,
    "page_size": 20,
    "has_more": true
  },
  "request_id": "req_5i6j7k8l9m0n"
}
```

### 12.6 添加群成员

```yaml
Method: POST
Path:   /api/v1/user-groups/{group_id}/members
Tags:   [用户群管理]
```

**Request Body:**

```json
{
  "user_ids": ["u_111111", "u_222222"],
  "role": "member"
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "group_id": "g_001",
    "added_count": 2,
    "skipped_count": 0,
    "members": [
      { "user_id": "u_111111", "role": "member", "joined_at": "2026-06-10T16:00:00Z" },
      { "user_id": "u_222222", "role": "member", "joined_at": "2026-06-10T16:00:00Z" }
    ]
  },
  "request_id": "req_6j7k8l9m0n1o"
}
```

### 12.7 移除群成员

```yaml
Method: DELETE
Path:   /api/v1/user-groups/{group_id}/members/{user_id}
Tags:   [用户群管理]
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "group_id": "g_001",
    "user_id": "u_111111",
    "removed_at": "2026-06-10T16:30:00Z"
  },
  "request_id": "req_7k8l9m0n1o2p"
}
```

### 12.8 批量更新群成员角色

```yaml
Method: PUT
Path:   /api/v1/user-groups/{group_id}/members/batch
Tags:   [用户群管理]
```

**Request Body:**

```json
{
  "updates": [
    { "user_id": "u_111111", "role": "admin" },
    { "user_id": "u_222222", "role": "member" }
  ]
}
```

**Response 200:**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "group_id": "g_001",
    "updated_count": 2
  },
  "request_id": "req_8l9m0n1o2p3q"
}
```

---

## 13. 统一错误码定义表

### 13.1 错误码结构

错误码采用 5 位数字编码：`{类别}{级别}{序号}`

- **第1位**: 服务类别
- **第2位**: 错误级别
- **第3-5位**: 具体序号

### 13.2 错误码总表

| 错误码 | 级别 | 含义 | HTTP Status | 说明 |
|--------|------|------|-------------|------|
| **全局通用 (0xxxx)** |||||
| `0` | Info | 成功 | 200 | 业务成功 |
| `10001` | Info | 部分成功 | 200 | 批量操作中部分失败 |
| **客户端错误 (4xxxx)** |||||
| `40000` | Warn | 请求参数错误 | 400 | 通用参数校验失败 |
| `40001` | Warn | 必填字段缺失 | 400 | 具体字段在 message 中说明 |
| `40002` | Warn | 参数格式错误 | 400 | JSON 解析失败或类型不匹配 |
| `40003` | Warn | 参数值不合法 | 400 | 超出枚举范围或长度超限 |
| `40004` | Warn | 分页参数错误 | 400 | page / page_size 超出限制 |
| `40005` | Warn | 文件格式不支持 | 400 | MIME 类型不在白名单 |
| `40006` | Warn | 文件大小超限 | 400 | 单文件超过 500MB |
| `40007` | Warn | 批量请求超限 | 400 | 批量操作数量超过上限 |
| `40008` | Warn | 幂等键重复 | 409 | Idempotency-Key 已被使用 |
| `40009` | Warn | API 子版本不存在 | 400 | X-API-Version 无效 |
| **认证授权 (401xx / 403xx)** |||||
| `40100` | Error | 认证失败 | 401 | 通用认证错误 |
| `40101` | Error | Token 过期或无效 | 401 | JWT 过期、签名错误或 revoked |
| `40102` | Error | 缺少认证信息 | 401 | 未携带 Authorization 头 |
| `40300` | Error | 权限不足 | 403 | 通用权限拒绝 |
| `40301` | Error | 无权访问知识库 | 403 | 用户群未配置该知识库权限 |
| `40302` | Error | 无权访问文档 | 403 | 文档级别权限拒绝 |
| `40303` | Error | 字段级权限拒绝 | 403 | 特定字段不可见 |
| `40304` | Error | 安全级别不足 | 403 | 用户安全等级低于内容等级 |
| `40305` | Error | 标签权限拒绝 | 403 | 用户群无权访问该标签内容 |
| `40306` | Error | 关键词拦截 | 403 | 请求/结果触发敏感关键词 |
| `40307` | Error | 文件类型权限拒绝 | 403 | 用户群被禁止访问该文件类型 |
| **资源错误 (404xx / 409xx)** |||||
| `40400` | Warn | 资源不存在 | 404 | 通用资源未找到 |
| `40401` | Warn | 知识库不存在 | 404 | kb_id 无效 |
| `40402` | Warn | 文档不存在 | 404 | doc_id 无效 |
| `40403` | Warn | 用户群不存在 | 404 | group_id 无效 |
| `40404` | Warn | 关键词不存在 | 404 | keyword_id 无效 |
| `40405` | Warn | 评测任务不存在 | 404 | task_id 无效 |
| `40900` | Warn | 资源冲突 | 409 | 通用资源冲突 |
| `40901` | Warn | 知识库名称已存在 | 409 | 同租户下名称重复 |
| `40902` | Warn | 文档已存在 | 409 | 同路径/同hash文档已存在 |
| `40903` | Warn | 用户已在群中 | 409 | 添加成员时已存在 |
| **服务端错误 (5xxxx)** |||||
| `50000` | Error | 内部服务器错误 | 500 | 通用服务端异常 |
| `50001` | Error | 数据库错误 | 500 | 数据库连接或查询失败 |
| `50002` | Error | 向量数据库错误 | 500 | Milvus 操作失败 |
| `50003` | Error | 缓存服务错误 | 500 | Redis 操作失败 |
| `50004` | Error | 外部 API 调用失败 | 502 | minimax-m3 等外部服务异常 |
| `50005` | Error | 文件存储错误 | 500 | 对象存储操作失败 |
| `50006` | Error | 消息队列错误 | 500 | Kafka / RabbitMQ 异常 |
| **异步任务 (6xxxx)** |||||
| `60001` | Info | 任务排队中 | 202 | 任务已提交，正在排队 |
| `60002` | Info | 任务处理中 | 202 | 任务正在异步执行 |
| `60003` | Warn | 任务失败 | 200 | 异步任务执行失败，见 data.detail |
| `60004` | Warn | 任务超时 | 200 | 异步任务执行超时 |
| `60005` | Warn | 任务取消 | 200 | 任务已被手动取消 |

### 13.3 错误响应示例

```json
{
  "code": 40306,
  "message": "检索结果触发敏感关键词拦截: '并购'",
  "data": {
    "blocked_keywords": ["并购"],
    "security_level": "L4",
    "user_level": "L2",
    "suggestion": "请联系管理员提升安全等级或调整检索范围"
  },
  "request_id": "req_9m0n1o2p3q4r"
}
```

---

## 14. Python SDK 示例

### 14.1 SDK 安装与初始化

```bash
pip install enterprise-rag-sdk
```

```python
from enterprise_rag import RAGClient

client = RAGClient(
    base_url="https://rag.company.com",
    api_key="sk-xxxxxxxxxxxxxxxx",
    timeout=60
)
```

### 14.2 知识库管理

```python
# 创建知识库
kb = client.knowledge_bases.create(
    name="产品研发知识库",
    description="技术方案与API文档",
    embedding_model="bge-m3",
    chunk_size=512
)
print(kb.id)  # kb_7a8b9c0d1e2f

# 列表查询
kbs = client.knowledge_bases.list(
    search="研发",
    page=1,
    page_size=20
)
for kb in kbs.items:
    print(kb.name, kb.document_count)

# 更新
client.knowledge_bases.update(
    kb_id="kb_7a8b9c0d1e2f",
    name="产品研发知识库 V2"
)

# 删除
client.knowledge_bases.delete(
    kb_id="kb_7a8b9c0d1e2f",
    force=False
)
```

### 14.3 文档上传与管理

```python
# 上传文件
with open("./部署手册.pdf", "rb") as f:
    task = client.documents.upload(
        kb_id="kb_7a8b9c0d1e2f",
        files=[f],
        security_level="L2",
        tags=["tag_001"]
    )
print(f"任务ID: {task.task_id}")

# 链接摄取
task = client.documents.ingest_link(
    kb_id="kb_7a8b9c0d1e2f",
    url="https://confluence.company.com/...",
    title="Confluence 技术方案"
)

# 重新索引
client.documents.reindex(
    kb_id="kb_7a8b9c0d1e2f",
    doc_id="doc_1a2b3c4d5e6f",
    chunk_size=1024
)
```

### 14.4 统一检索

```python
results = client.search.query(
    query="如何配置负载均衡？",
    kb_ids=["kb_7a8b9c0d1e2f"],
    search_type="hybrid",
    top_k=10,
    filters={
        "security_levels": ["L1", "L2"],
        "tags": ["tag_001"]
    },
    rerank={
        "enabled": True,
        "model": "bge-reranker-large",
        "top_n": 5
    },
    highlight={
        "enabled": True,
        "pre_tag": "<mark>",
        "post_tag": "</mark>"
    }
)

for r in results.results:
    print(f"[Rank {r.rank}] Score: {r.rerank_score}")
    print(f"来源: {r.document.filename}")
    print(f"内容: {r.chunk.text_highlighted}")
```

### 14.5 非流式问答

```python
response = client.chat.completions.create(
    model="rag-default",
    messages=[
        {"role": "system", "content": "你是企业知识库助手。"},
        {"role": "user", "content": "如何配置负载均衡？"}
    ],
    kb_ids=["kb_7a8b9c0d1e2f"],
    temperature=0.3,
    search_params={
        "top_k": 10,
        "rerank": {"enabled": True, "top_n": 5}
    },
    citation={"enabled": True, "format": "markdown"}
)

print(response.choices[0].message.content)
print("引用:", response.retrieval_info.citations)
```

### 14.6 SSE 流式问答

```python
stream = client.chat.completions.create(
    model="rag-default",
    messages=[{"role": "user", "content": "如何配置负载均衡？"}],
    kb_ids=["kb_7a8b9c0d1e2f"],
    stream=True
)

for event in stream:
    if event.type == "message":
        print(event.delta.content, end="", flush=True)
    elif event.type == "done":
        print(f"\n[总计 Token: {event.usage.total_tokens}]")
    elif event.type == "error":
        print(f"\n[错误: {event.error.code}] {event.error.message}")
```

### 14.7 异常处理

```python
from enterprise_rag.exceptions import (
    RAGAPIError,
    RAGAuthError,
    RAGPermissionError,
    RAGNotFoundError
)

try:
    result = client.search.query(query="test", kb_ids=["kb_invalid"])
except RAGPermissionError as e:
    print(f"权限不足: {e.code} - {e.message}")
except RAGNotFoundError as e:
    print(f"资源不存在: {e.message}")
except RAGAPIError as e:
    print(f"API 错误: {e.status_code} - {e.message}")
    print(f"Request ID: {e.request_id}")
```

---

## 15. JavaScript SDK 示例

### 15.1 SDK 安装与初始化

```bash
npm install @company/enterprise-rag-sdk
```

```typescript
import { RAGClient } from '@company/enterprise-rag-sdk';

const client = new RAGClient({
  baseURL: 'https://rag.company.com',
  apiKey: 'sk-xxxxxxxxxxxxxxxx',
  timeout: 60000,
});
```

### 15.2 知识库管理

```typescript
// 创建知识库
const kb = await client.knowledgeBases.create({
  name: '产品研发知识库',
  description: '技术方案与API文档',
  embeddingModel: 'bge-m3',
  chunkSize: 512,
});
console.log(kb.id); // kb_7a8b9c0d1e2f

// 列表查询（支持 async iterator）
const kbs = await client.knowledgeBases.list({
  search: '研发',
  page: 1,
  pageSize: 20,
});
for (const kb of kbs.items) {
  console.log(kb.name, kb.documentCount);
}

// 更新
await client.knowledgeBases.update('kb_7a8b9c0d1e2f', {
  name: '产品研发知识库 V2',
});

// 删除
await client.knowledgeBases.delete('kb_7a8b9c0d1e2f', { force: false });
```

### 15.3 文档上传

```typescript
import { createReadStream } from 'fs';

// 上传文件
const task = await client.documents.upload({
  kbId: 'kb_7a8b9c0d1e2f',
  files: [createReadStream('./部署手册.pdf')],
  securityLevel: 'L2',
  tags: ['tag_001'],
});
console.log(`任务ID: ${task.taskId}`);

// 轮询任务状态
const doc = await client.tasks.poll(task.taskId, {
  interval: 2000,
  timeout: 300000,
});
console.log(`文档状态: ${doc.status}`);

// 链接摄取
const linkTask = await client.documents.ingestLink({
  kbId: 'kb_7a8b9c0d1e2f',
  url: 'https://confluence.company.com/...',
  title: 'Confluence 技术方案',
});
```

### 15.4 统一检索

```typescript
const result = await client.search.query({
  query: '如何配置负载均衡？',
  kbIds: ['kb_7a8b9c0d1e2f'],
  searchType: 'hybrid',
  topK: 10,
  filters: {
    securityLevels: ['L1', 'L2'],
    tags: ['tag_001'],
  },
  rerank: {
    enabled: true,
    model: 'bge-reranker-large',
    topN: 5,
  },
  highlight: {
    enabled: true,
    preTag: '<mark>',
    postTag: '</mark>',
  },
});

for (const r of result.results) {
  console.log(`[Rank ${r.rank}] Score: ${r.rerankScore}`);
  console.log(`来源: ${r.document.filename}`);
  console.log(`内容: ${r.chunk.textHighlighted}`);
}
```

### 15.5 非流式问答

```typescript
const response = await client.chat.completions.create({
  model: 'rag-default',
  messages: [
    { role: 'system', content: '你是企业知识库助手。' },
    { role: 'user', content: '如何配置负载均衡？' },
  ],
  kbIds: ['kb_7a8b9c0d1e2f'],
  temperature: 0.3,
  searchParams: {
    topK: 10,
    rerank: { enabled: true, topN: 5 },
  },
  citation: { enabled: true, format: 'markdown' },
});

console.log(response.choices[0].message.content);
console.log('引用:', response.retrievalInfo.citations);
```

### 15.6 SSE 流式问答（EventSource / Fetch）

```typescript
// 使用 SDK 内置的流式接口
const stream = await client.chat.completions.create({
  model: 'rag-default',
  messages: [{ role: 'user', content: '如何配置负载均衡？' }],
  kbIds: ['kb_7a8b9c0d1e2f'],
  stream: true,
});

for await (const event of stream) {
  switch (event.type) {
    case 'message':
      process.stdout.write(event.delta.content ?? '');
      break;
    case 'retrieval':
      console.log('\n[检索完成]', event.retrievalInfo);
      break;
    case 'done':
      console.log(`\n[总计 Token: ${event.usage.totalTokens}]`);
      break;
    case 'error':
      console.error(`\n[错误: ${event.error.code}] ${event.error.message}`);
      break;
  }
}

// 原生 fetch + ReadableStream 示例（浏览器环境）
async function streamChat() {
  const res = await fetch('https://rag.company.com/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer sk-xxx',
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({
      model: 'rag-default',
      messages: [{ role: 'user', content: '如何配置负载均衡？' }],
      kbIds: ['kb_7a8b9c0d1e2f'],
      stream: true,
    }),
  });

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    // 解析 SSE 格式
    for (const line of chunk.split('\n')) {
      if (line.startsWith('data:')) {
        const data = JSON.parse(line.slice(5).trim());
        if (data.choices?.[0]?.delta?.content) {
          process.stdout.write(data.choices[0].delta.content);
        }
      }
    }
  }
}
```

### 15.7 用户群管理

```typescript
// 创建用户群
const group = await client.userGroups.create({
  name: '安全合规组',
  description: '负责安全合规审查的人员',
  securityLevelCeiling: 'L4',
  initialMemberIds: ['u_123456', 'u_789012'],
});

// 添加成员
await client.userGroups.addMembers('g_001', {
  userIds: ['u_111111', 'u_222222'],
  role: 'member',
});

// 获取成员列表
const members = await client.userGroups.listMembers('g_001', {
  page: 1,
  pageSize: 20,
});
```

### 15.8 错误处理

```typescript
import { RAGError, RAGPermissionError, RAGNotFoundError } from '@company/enterprise-rag-sdk';

try {
  await client.search.query({ query: 'test', kbIds: ['kb_invalid'] });
} catch (err) {
  if (err instanceof RAGPermissionError) {
    console.error('权限不足:', err.code, err.message);
  } else if (err instanceof RAGNotFoundError) {
    console.error('资源不存在:', err.message);
  } else if (err instanceof RAGError) {
    console.error('API 错误:', err.statusCode, err.message);
    console.error('Request ID:', err.requestId);
  } else {
    console.error('未知错误:', err);
  }
}
```

---

## 16. OpenAPI 3.0 片段

### 16.1 统一响应组件

```yaml
openapi: 3.0.3
info:
  title: Enterprise RAG API
  version: 1.0.0
  description: 企业级私有化多模态 RAG 知识库系统 API

components:
  schemas:
    UnifiedResponse:
      type: object
      required: [code, message, data, request_id]
      properties:
        code:
          type: integer
          description: 业务错误码，0 表示成功
          example: 0
        message:
          type: string
          description: 提示信息
          example: "success"
        data:
          type: object
          nullable: true
          description: 业务数据
        request_id:
          type: string
          description: 请求唯一标识，用于链路追踪
          example: "req_7f8a9b2c3d4e"

    PaginatedData:
      type: object
      properties:
        items:
          type: array
          items:
            type: object
        total:
          type: integer
          example: 128
        page:
          type: integer
          example: 1
        page_size:
          type: integer
          example: 20
        has_more:
          type: boolean
          example: true

    KnowledgeBase:
      type: object
      properties:
        id:
          type: string
          example: "kb_7a8b9c0d1e2f"
        name:
          type: string
          example: "产品研发知识库"
        description:
          type: string
        status:
          type: string
          enum: [active, frozen, archived]
        embedding_model:
          type: string
          example: "bge-m3"
        chunk_size:
          type: integer
          example: 512
        chunk_overlap:
          type: integer
          example: 50
        rerank_model:
          type: string
          example: "bge-reranker-base"
        document_count:
          type: integer
          example: 42
        total_chunks:
          type: integer
          example: 3580
        storage_used_bytes:
          type: integer
          example: 268435456
        metadata:
          type: object
        default_security_level:
          type: string
          enum: [L0, L1, L2, L3, L4]
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
        created_by:
          type: string

    SearchResult:
      type: object
      properties:
        rank:
          type: integer
        score:
          type: number
          format: float
        rerank_score:
          type: number
          format: float
        chunk:
          type: object
          properties:
            id:
              type: string
            doc_id:
              type: string
            kb_id:
              type: string
            text:
              type: string
            text_highlighted:
              type: string
            token_count:
              type: integer
            security_level:
              type: string
            metadata:
              type: object
        document:
          type: object
          properties:
            id:
              type: string
            filename:
              type: string
            mime_type:
              type: string
            tags:
              type: array
              items:
                type: object

    ChatMessage:
      type: object
      properties:
        role:
          type: string
          enum: [system, user, assistant]
        content:
          type: string

    ChatCompletionRequest:
      type: object
      required: [model, messages]
      properties:
        model:
          type: string
          example: "rag-default"
        messages:
          type: array
          items:
            $ref: '#/components/schemas/ChatMessage'
        kb_ids:
          type: array
          items:
            type: string
        stream:
          type: boolean
          default: false
        temperature:
          type: number
          format: float
          default: 0.3
        max_tokens:
          type: integer
          default: 2048
        search_params:
          type: object
        context_compression:
          type: object
        citation:
          type: object

    SSEChunk:
      type: object
      properties:
        id:
          type: string
        object:
          type: string
          example: "chat.completion.chunk"
        created:
          type: integer
        model:
          type: string
        choices:
          type: array
          items:
            type: object
            properties:
              index:
                type: integer
              delta:
                type: object
              finish_reason:
                type: string
                nullable: true

  parameters:
    PageParam:
      in: query
      name: page
      schema:
        type: integer
        default: 1
    PageSizeParam:
      in: query
      name: page_size
      schema:
        type: integer
        default: 20
        maximum: 100
    KbIdPath:
      in: path
      name: kb_id
      required: true
      schema:
        type: string
    DocIdPath:
      in: path
      name: doc_id
      required: true
      schema:
        type: string

  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

security:
  - BearerAuth: []

paths:
  /api/v1/knowledge-bases:
    post:
      summary: 创建知识库
      tags: [知识库管理]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/KnowledgeBase'
      responses:
        '201':
          description: 创建成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/UnifiedResponse'
                  - properties:
                      data:
                        $ref: '#/components/schemas/KnowledgeBase'
    get:
      summary: 获取知识库列表
      tags: [知识库管理]
      parameters:
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/PageSizeParam'
      responses:
        '200':
          description: 查询成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/UnifiedResponse'
                  - properties:
                      data:
                        $ref: '#/components/schemas/PaginatedData'

  /api/v1/search:
    post:
      summary: 统一检索
      tags: [检索引擎]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                query:
                  type: string
                kb_ids:
                  type: array
                  items:
                    type: string
                search_type:
                  type: string
                  enum: [dense, sparse, hybrid, image]
                top_k:
                  type: integer
                filters:
                  type: object
                rerank:
                  type: object
                highlight:
                  type: object
      responses:
        '200':
          description: 检索成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/UnifiedResponse'
                  - properties:
                      data:
                        type: object
                        properties:
                          results:
                            type: array
                            items:
                              $ref: '#/components/schemas/SearchResult'

  /api/v1/chat/completions:
    post:
      summary: 问答（支持 SSE 流式）
      tags: [问答引擎]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ChatCompletionRequest'
      responses:
        '200':
          description: 非流式响应
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UnifiedResponse'
        '200-sse':
          description: SSE 流式响应
          content:
            text/event-stream:
              schema:
                type: string
                example: |
                  event: message
                  data: {"id":"...","choices":[{"delta":{"content":"根据"}}]}

                  event: done
                  data: {"usage":{"total_tokens":1779}}
```

### 16.2 路径与标签汇总

```yaml
tags:
  - name: 知识库管理
    description: 知识库的 CRUD 操作
  - name: 文档管理
    description: 文档上传、链接摄取、索引管理
  - name: 检索引擎
    description: 向量检索、混合检索、以图搜图
  - name: 问答引擎
    description: 非流式与 SSE 流式问答
  - name: 权限管理
    description: 五级权限体系的配置与校验
  - name: 评测系统
    description: RAG 效果评测与对比实验
  - name: 关键词管理
    description: 敏感关键词的分级配置
  - name: 用户群管理
    description: 用户群与成员管理
```

---

## 附录 A: 快速参考卡片

### A.1 全量 API 路径速查

| 功能 | Method | Path |
|------|--------|------|
| 创建知识库 | POST | `/api/v1/knowledge-bases` |
| 知识库列表 | GET | `/api/v1/knowledge-bases` |
| 知识库详情 | GET | `/api/v1/knowledge-bases/{kb_id}` |
| 更新知识库 | PUT | `/api/v1/knowledge-bases/{kb_id}` |
| 删除知识库 | DELETE | `/api/v1/knowledge-bases/{kb_id}` |
| 上传文档 | POST | `/api/v1/knowledge-bases/{kb_id}/documents` |
| 链接摄取 | POST | `/api/v1/knowledge-bases/{kb_id}/documents/link` |
| 文档列表 | GET | `/api/v1/knowledge-bases/{kb_id}/documents` |
| 文档详情 | GET | `/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}` |
| 删除文档 | DELETE | `/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}` |
| 重新索引 | POST | `/api/v1/knowledge-bases/{kb_id}/documents/{doc_id}/reindex` |
| 统一检索 | POST | `/api/v1/search` |
| 以图搜图 | POST | `/api/v1/search/image` |
| 问答 | POST | `/api/v1/chat/completions` |
| 文档权限 | POST | `/api/v1/permissions/documents` |
| 字段权限 | POST | `/api/v1/permissions/fields` |
| 标签权限 | POST | `/api/v1/permissions/tags` |
| 群权限 | POST | `/api/v1/permissions/groups` |
| 权限校验 | POST | `/api/v1/permissions/check` |
| 提交评测 | POST | `/api/v1/evaluation/tasks` |
| 评测结果 | GET | `/api/v1/evaluation/tasks/{task_id}` |
| 对比评测 | POST | `/api/v1/evaluation/compare` |
| 关键词列表 | GET | `/api/v1/keywords` |
| 创建关键词 | POST | `/api/v1/keywords` |
| 更新关键词 | PUT | `/api/v1/keywords/{keyword_id}` |
| 删除关键词 | DELETE | `/api/v1/keywords/{keyword_id}` |
| 批量导入关键词 | POST | `/api/v1/keywords/batch` |
| 用户群列表 | GET | `/api/v1/user-groups` |
| 创建用户群 | POST | `/api/v1/user-groups` |
| 更新用户群 | PUT | `/api/v1/user-groups/{group_id}` |
| 删除用户群 | DELETE | `/api/v1/user-groups/{group_id}` |
| 群成员列表 | GET | `/api/v1/user-groups/{group_id}/members` |
| 添加群成员 | POST | `/api/v1/user-groups/{group_id}/members` |
| 移除群成员 | DELETE | `/api/v1/user-groups/{group_id}/members/{user_id}` |
| 批量更新角色 | PUT | `/api/v1/user-groups/{group_id}/members/batch` |

### A.2 状态码速查

| HTTP Status | 含义 | 典型场景 |
|-------------|------|----------|
| 200 | 成功 | GET/PUT/DELETE 成功，列表查询 |
| 201 | 已创建 | POST 创建资源成功 |
| 202 | 已接受 | 异步任务提交（文档上传、评测） |
| 400 | 请求参数错误 | 参数校验失败 |
| 401 | 未认证 | Token 缺失、过期、无效 |
| 403 | 权限不足 | 五级权限任意一层拒绝 |
| 404 | 资源不存在 | kb_id / doc_id 等无效 |
| 409 | 资源冲突 | 名称重复、成员已存在 |
| 410 | 已下线 | API 主版本已弃用 |
| 429 | 请求过于频繁 | 限流触发 |
| 500 | 服务器内部错误 | 通用服务端异常 |
| 502 | 网关错误 | 外部 API（minimax-m3）调用失败 |
| 503 | 服务不可用 | 向量数据库或消息队列异常 |

---

> 本文档作为企业级私有化多模态 RAG 系统的统一 API 接口规范，所有服务端实现、SDK 生成、前端联调均以此为准。版本迭代时，向后兼容的变更通过 `X-API-Version` 头控制；不兼容的变更通过 URL 主版本号升级（如 `/api/v2/...`）实现。
