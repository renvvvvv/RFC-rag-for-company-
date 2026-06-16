# Kong 网关路由测试报告

**测试时间：** 2026-06-16 03:10 - 03:12 UTC  
**测试环境：** Windows + Git Bash，Kong 容器 `rag-kong`（kong:3.5）运行在 Docker Compose 中  
**Kong 代理端口：** `:8000`  
**Kong Admin 端口：** `:8001`

---

## 1. `kong.yml` 配置摘要

读取项目根目录 `kong.yml`，为 **DB-less 声明式配置**（`_format_version: "3.0"`）。

### Services（2 个）

| Service | Upstream URL | 用途 |
|---------|--------------|------|
| `app-backend` | `http://app-backend:8080` | 后端 FastAPI 服务 |
| `frontend` | `http://frontend:80` | 前端 Nginx 服务 |

### Routes（3 个）

| 名称 | Service | Paths | strip_path | preserve_host |
|------|---------|-------|------------|---------------|
| `app-backend-api` | `app-backend` | `/api` | `false` | `false` |
| `app-backend-docs` | `app-backend` | `/docs`, `/openapi.json` | `false` | `false` |
| `frontend-root` | `frontend` | `/` | `false` | `false` |

### Plugins（全局生效）

| Plugin | 配置 | 状态 |
|--------|------|------|
| `rate-limiting` | `minute: 100`, `policy: local`, `fault_tolerant: true` | ✅ 已启用 |
| `prometheus` | 默认配置 | ✅ 已启用 |

### 未启用 / 注释项

- `key-auth`：被注释掉，当前 demo 环境未启用，符合 `kong.yml` 中的说明。
- **未配置 `cors` plugin**。

### Consumers（1 个）

- `default-consumer`，附带 `keyauth_credentials: placeholder-api-key`（因 `key-auth` 未启用，当前不生效）。

---

## 2. 测试用例结果

| # | 测试项 | 请求 | 预期 | 实际状态码 | 实际响应摘要 | 结果 |
|---|--------|------|------|------------|--------------|------|
| 1 | 读取 `kong.yml` | - | services/routes/plugins 完整 | 见上方摘要 | 2 services、3 routes、2 plugins、1 consumer | ✅ PASS |
| 2 | 前端首页 | `GET http://localhost:8000/` | 返回前端 HTML | `200` | `<!doctype html>...企业级私有化多模态 RAG...</title>`，Server: nginx/1.29.8 | ✅ PASS |
| 3 | 后端健康检查（带尾斜杠） | `GET http://localhost:8000/api/v1/health/` | 转发到后端健康检查 | `307` | `Location: http://app-backend:8080/api/v1/health` | ⚠️ NOTE |
| 4 | 后端健康检查（不带尾斜杠） | `GET http://localhost:8000/api/v1/health` | 返回健康 JSON | `200` | `{"status":"ok","services":{"postgres":...}}` | ✅ PASS |
| 5 | Kong 自身状态 | `GET http://localhost:8001/status` | Kong Admin 返回状态 JSON | `200` | connections、memory、workers 等统计正常 | ✅ PASS |
| 6 | CORS 配置检查 | `OPTIONS http://localhost:8000/api/v1/auth/login/` + Origin | Kong/后端返回 CORS 预检响应 | `200` | 返回 `access-control-allow-origin: http://example.com` 等 CORS 头 | ⚠️ PARTIAL |
| 7 | 错误密码登录透传 | `POST http://localhost:8000/api/v1/auth/login/`（form: wrong password） | Kong 透传，后端返回 401 | 尾斜杠请求 `307`；无尾杠 `/api/v1/auth/login` 为 `401` | `{"detail":"用户名或密码错误"}` | ⚠️ PARTIAL |
| 8 | Kong 日志检查 | `docker logs rag-kong` | 无路由失败/超时 | 仅见 `GET /metrics` 与本次测试访问日志，无 error/timeout/5xx | ✅ PASS |

> **补充说明：**
> - 测试 7 中，使用 JSON body 会被后端 FastAPI OAuth2 表单拒绝（`422`）；改用 `application/x-www-form-urlencoded`（`username=test&password=wrong`）后，Kong 正确透传并返回 `401`，证明认证流量未被网关拦截。
> - 所有通过 Kong 的响应均携带 `X-RateLimit-*` 头，说明 `rate-limiting` plugin 生效。

---

## 3. 发现的问题

### 3.1 尾斜杠导致 307，且 `Location` 暴露内部服务地址

- `GET /api/v1/health/` 与 `POST /api/v1/auth/login/` 均被后端返回 `307 Temporary Redirect`。
- `Location` 头指向 `http://app-backend:8080/...`，这是 Docker 内部服务名，外部客户端无法解析，会导致浏览器/客户端重定向失败。
- 根本原因是：
  1. FastAPI 默认开启 `redirect_slashes=True`，当路径以 `/` 结尾但路由未以 `/` 结尾时返回 307。
  2. Kong route 的 `preserve_host: false`，上游看到的是 `Host: app-backend:8080`，因此 FastAPI 生成的 redirect URL 使用内部主机名。

### 3.2 Kong 未统一配置 CORS

- Kong 当前没有 `cors` plugin，CORS 由后端（FastAPI / uvicorn）自行处理。
- 本次 `OPTIONS` 测试返回了正确的 CORS 头，说明后端已做处理；但依赖后端意味着：
  - 不同路由（如 `/docs`、`/openapi.json`）的 CORS 行为可能不一致。
  - 生产环境中难以统一控制允许的 Origin、Methods、Headers、Credentials。

### 3.3 `rate-limiting` 使用 `policy: local`

- 当前为单节点 Kong，使用 local 策略无问题；若后续水平扩展 Kong，需改为 `redis` 策略，否则限流无法共享计数。

---

## 4. 修复建议

### 4.1 修复尾斜杠与内部地址暴露（推荐组合方案）

**方案 A：在 Kong 层保留原始 Host（最轻量）**

对后端路由启用 `preserve_host: true`：

```yaml
routes:
  - name: app-backend-api
    paths:
      - /api
    strip_path: false
    preserve_host: true   # 新增
  - name: app-backend-docs
    paths:
      - /docs
      - /openapi.json
    strip_path: false
    preserve_host: true   # 新增
```

这样 FastAPI 生成的 `Location` 将变为 `http://localhost:8000/api/v1/health`，外部客户端可正常跟随。

**方案 B：关闭 FastAPI 自动尾斜杠重定向（代码层）**

```python
app = FastAPI(redirect_slashes=False)
```

此时请求 `/api/v1/health/` 会直接返回 `404`，需要前端/客户端统一使用无尾杠 URL。

**建议：** 同时采用 **方案 A + 统一 API 调用规范**（前端始终调用 `/api/v1/health`、`/api/v1/auth/login` 等无尾杠地址），既保留兼容性，又避免内部主机名泄露。

### 4.2 在 Kong 添加全局 CORS plugin

```yaml
plugins:
  - name: cors
    config:
      origins:
        - "http://localhost:3000"   # 前端开发地址
        - "https://your-domain.com"  # 生产域名
      methods:
        - GET
        - POST
        - PUT
        - PATCH
        - DELETE
        - OPTIONS
      headers:
        - Authorization
        - Content-Type
        - X-Request-ID
      exposed_headers:
        - X-Request-ID
      credentials: true
      max_age: 3600
```

添加后，可关闭后端重复的 CORS 处理，统一由网关负责。

### 4.3 生产前启用认证

- 当前 `key-auth` 被注释，适合本地 demo。
- 生产环境应取消注释，并为每个前端会话分发 API key，或在 Kong 配置 `openid-connect` / `jwt` plugin。

### 4.4 限流策略扩展

如需多 Kong 节点：

```yaml
- name: rate-limiting
  config:
    minute: 100
    policy: redis
    redis_host: rag-redis
    redis_port: 6379
```

---

## 5. 结论

- **Kong 网关本身运行正常**，`:8000` 能正确将 `/` 路由到前端、`/api/*` 路由到后端，`:8001/status` 正常，日志无路由失败或超时。
- **主要问题集中在尾斜杠 307 重定向**，它暴露了内部服务名 `app-backend:8080`，可能导致外部客户端调用失败。
- **CORS 当前由后端处理**，建议在 Kong 层统一配置以提升可维护性。
- 按上述 4.1 与 4.2 修改 `kong.yml` 后，重新加载 Kong 配置（`docker compose restart rag-kong` 或 `kong reload`）即可生效。
