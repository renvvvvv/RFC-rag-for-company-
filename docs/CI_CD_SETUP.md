# CI/CD 配置说明

项目已配置 GitHub Actions 自动流水线，覆盖代码检查、安全扫描、镜像构建、服务器部署四个阶段。

## 文件位置

- 工作流文件：`.github/workflows/ci-cd.yml`
- 部署脚本：`scripts/deploy.sh`（可选）
- 镜像标签配置：`docker-compose.yml` 中的 `BACKEND_IMAGE`、`FRONTEND_IMAGE`、`IMAGE_TAG`

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
| `DEPLOY_PATH` | 服务器上项目存放路径 | `/opt/rag-system` |

## 服务器准备

在目标服务器上执行：

```bash
# 1. 克隆项目
git clone https://github.com/yourname/rag-system.git /opt/rag-system
cd /opt/rag-system

# 2. 创建环境配置文件（必须！）
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入真实的数据库、模型服务地址和密钥

# 3. 安装 Docker 和 Docker Compose
# Ubuntu/Debian 示例
curl -fsSL https://get.docker.com | sh

# 4. 配置当前用户免密使用 docker
sudo usermod -aG docker $USER

# 5. 将部署用户的 SSH 公钥添加到 authorized_keys
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
```

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
| push 到 `main` | 全部四个阶段 |
| push 到 `develop` | lint-and-test |

## 部署后验证

流水线最后会执行健康检查，你也可以手动访问：

```bash
ssh <user>@<host>
cd /opt/rag-system
docker compose ps
curl http://localhost:8080/api/v1/health
```

## 常见问题

1. **部署时 docker login 失败**
   - 检查 `REGISTRY_URL`、`REGISTRY_USERNAME`、`REGISTRY_PASSWORD` 是否正确。

2. **SSH 连接失败**
   - 确认 `SSH_PRIVATE_KEY` 是**私钥**，不是公钥。
   - 确认服务器 `~/.ssh/authorized_keys` 已包含对应公钥。

3. **健康检查失败**
   - 检查 `backend/.env` 是否配置了正确的数据库和模型服务地址。
   - 查看日志：`docker compose logs -f app-backend`
