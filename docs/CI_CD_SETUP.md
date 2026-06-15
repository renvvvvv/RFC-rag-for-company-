# CI/CD 配置说明

项目已配置 GitHub Actions 自动流水线，覆盖代码检查、安全扫描、镜像构建、**蓝绿部署**四个阶段。

## 文件位置

- 工作流文件：`.github/workflows/ci-cd.yml`
- 蓝绿部署脚本：`scripts/blue-green-deploy.sh`
- 回滚脚本：`scripts/rollback.sh`
- 基础设施编排：`docker-compose.infra.yml`
- 应用层编排：`docker-compose.app.yml`
- 本地/开发一键启动：`docker-compose.yml`

## 蓝绿部署架构

服务器上会存在两个独立的应用部署目录：

```
/opt/rag-system              # 基础目录，存放共享基础设施 compose 和 .active-color 标记
/opt/rag-system-blue         # 蓝色应用副本
/opt/rag-system-green        # 绿色应用副本
```

共享基础设施（PostgreSQL、Redis、RabbitMQ、Milvus、MinIO、Prometheus、Grafana）只运行一份：

```bash
cd /opt/rag-system
docker compose -f docker-compose.infra.yml up -d
```

应用层（Kong、backend、frontend、workers）在两个颜色目录中独立运行，端口互不冲突：

| 颜色 | Kong Proxy | Frontend | Backend |
|------|-----------|----------|---------|
| blue  | 8000 | 3002 | 8080 |
| green | 8002 | 3003 | 8081 |

当前活跃颜色记录在 `/opt/rag-system/.active-color` 文件中。

## 部署流程

1. CI/CD 推送镜像到镜像仓库
2. SSH 到服务器
3. 拉取最新代码到 `/opt/rag-system`
4. 运行 `scripts/blue-green-deploy.sh`
   - 确定当前 inactive 颜色
   - 在 inactive 目录中部署新版本
   - 启动 inactive 颜色
   - 对 inactive 颜色执行健康检查
   - 健康检查通过后，切换 `.active-color` 标记
   - 停止旧颜色
5. 如果失败，自动运行 `scripts/rollback.sh` 切回旧颜色

## GitHub Secrets 配置

进入 GitHub 仓库 **Settings → Secrets and variables → Actions**，添加以下 secrets：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `REGISTRY_URL` | 镜像仓库地址，Docker Hub 可留空 | `docker.io` 或 `registry.cn-shanghai.aliyuncs.com` |
| `REGISTRY_USERNAME` | 镜像仓库用户名 | `your-dockerhub-username` |
| `REGISTRY_PASSWORD` | 镜像仓库密码或 token | `dckr_pat_xxx` |
| `BACKEND_IMAGE` | 后端镜像完整名称 | `yourname/rag-backend` |
| `FRONTEND_IMAGE` | 前端镜像完整名称 | `yourname/rag-frontend` |
| `SSH_HOST` | 部署目标服务器 IP 或域名 | `124.251.122.166` |
| `SSH_USERNAME` | SSH 登录用户名 | `root` |
| `SSH_PRIVATE_KEY` | SSH 私钥（对应服务器 authorized_keys） | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DEPLOY_PATH` | 服务器上项目基础目录 | `/opt/rag-system` |

## 服务器准备

在目标服务器上执行：

```bash
# 1. 克隆基础仓库（只需要一个基础目录）
git clone https://github.com/renvvvvv/RFC-rag-for-company-.git /opt/rag-system
cd /opt/rag-system

# 2. 创建环境配置文件（必须！只创建一次）
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入真实的数据库、模型服务地址和密钥

# 3. 安装 Docker 和 Docker Compose（如未安装）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重新登录使权限生效

# 4. 启动共享基础设施
docker compose -f docker-compose.infra.yml up -d

# 5. 将部署用户的 SSH 公钥添加到 authorized_keys
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
```

> 注意：蓝绿部署脚本**不会**自动安装 Docker，如果 Docker 不存在会直接报错退出。

## 镜像仓库选择

### Docker Hub

- `REGISTRY_URL` 留空或用 `docker.io`
- `BACKEND_IMAGE`：`yourname/rag-backend`
- `FRONTEND_IMAGE`：`yourname/rag-frontend`

### 阿里云 ACR（推荐国内）

- `REGISTRY_URL`：`registry.cn-shanghai.aliyuncs.com`
- `BACKEND_IMAGE`：`your-namespace/rag-backend`
- `FRONTEND_IMAGE`：`your-namespace/rag-frontend`
- `REGISTRY_USERNAME`：阿里云账号
- `REGISTRY_PASSWORD`：ACR 固定密码或临时 token

## 触发条件

| 事件 | 触发阶段 |
|------|----------|
| PR 到 `main` | lint-and-test、security-scan |
| push 到 `main` | 全部四个阶段（包括蓝绿部署） |
| push 到 `develop` | lint-and-test |

## 手动切换颜色

如果 CI/CD 之外需要手动切换，可以在服务器上执行：

```bash
cd /opt/rag-system
bash scripts/blue-green-deploy.sh green   # 部署/切换到 green
bash scripts/blue-green-deploy.sh blue    # 部署/切换到 blue
```

## 手动回滚

```bash
cd /opt/rag-system
bash scripts/rollback.sh
```

## 访问地址

部署完成后，通过当前活跃颜色访问：

```bash
ACTIVE=$(cat /opt/rag-system/.active-color)
echo "Active color: $ACTIVE"
# 如果 active 是 blue
open http://localhost:8000
# 如果 active 是 green
open http://localhost:8002
```

## 安全说明

- `.env` 文件永远不会被 CI/CD 覆盖
- 不自动安装任何系统级软件
- 不清理其他项目的 Docker 镜像
- 部署失败时旧颜色仍然保持运行，可立即回滚
- 共享基础设施与应用层分离，蓝绿切换不影响数据库和消息队列

## 常见问题

1. **部署时 docker login 失败**
   - 检查 `REGISTRY_URL`、`REGISTRY_USERNAME`、`REGISTRY_PASSWORD` 是否正确。

2. **SSH 连接失败**
   - 确认 `SSH_PRIVATE_KEY` 是**私钥**，不是公钥。
   - 确认服务器 `~/.ssh/authorized_keys` 已包含对应公钥。

3. **健康检查失败**
   - 检查 `backend/.env` 是否配置了正确的数据库和模型服务地址。
   - 查看日志：`cd /opt/rag-system-$ACTIVE && docker compose -f docker-compose.app.yml logs -f app-backend`

4. **端口冲突**
   - 确保 8000/8001/8002/8003/8080/8081/3002/3003 未被其他服务占用。
