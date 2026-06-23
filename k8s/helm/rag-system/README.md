# RAG System Kubernetes Helm Chart

本 Helm Chart 用于在 Kubernetes 上部署企业级私有化多模态 RAG 系统，同时保留原有 `docker-compose.yml` 部署方式。

## 目录

- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [生产部署建议](#生产部署建议)
- [常用命令](#常用命令)
- [故障排查](#故障排查)

## 前置条件

- Kubernetes 1.25+
- Helm 3.12+
- Ingress Controller（如 ingress-nginx，可选）
- kubectl 已配置并能访问目标集群
- 容器镜像仓库可访问（默认使用 Docker Hub 占位符仓库，需替换）

## 快速开始

### 1. 生成密钥文件

从 `backend/.env` 自动生成 `secrets.yaml`：

```bash
bash k8s/helm/rag-system/generate-secrets.sh
```

或手动复制模板并编辑：

```bash
cp k8s/helm/rag-system/secrets.yaml.example k8s/helm/rag-system/secrets.yaml
# 编辑 secrets.yaml，替换所有占位密码和 API Key
```

### 2. 安装 Chart

```bash
cd k8s/helm/rag-system
bash upgrade.sh rag-system rag-system
```

或使用 helm 命令：

```bash
helm upgrade --install rag-system ./rag-system \
  -n rag-system --create-namespace \
  -f ./rag-system/values.yaml \
  -f ./rag-system/secrets.yaml
```

### 3. 查看部署状态

```bash
kubectl get pods -n rag-system
kubectl get svc -n rag-system
```

### 4. 本地访问

如果没有启用 Ingress，使用端口转发：

```bash
# Kong 网关入口
kubectl port-forward svc/rag-system-kong 8000:8000 -n rag-system

# Grafana
kubectl port-forward svc/rag-system-grafana 3001:3000 -n rag-system

# Prometheus
kubectl port-forward svc/rag-system-prometheus 9090:9090 -n rag-system
```

浏览器访问：

- 前端 + API：`http://localhost:8000`
- Grafana：`http://localhost:3001`（默认账号/密码见 `secrets.yaml`）
- Prometheus：`http://localhost:9090`

## 配置说明

### 镜像仓库

编辑 `values.yaml` 或创建自定义 values 文件覆盖：

```yaml
appBackend:
  image:
    repository: your-registry/rag-backend
    tag: v1.2.3

frontend:
  image:
    repository: your-registry/rag-frontend
    tag: v1.2.3

workers:
  image:
    repository: your-registry/rag-worker
    tag: v1.2.3
```

### 有状态服务开关

Chart 默认内置 PostgreSQL、Redis、RabbitMQ、etcd、MinIO、Milvus standalone，适合开发和 POC。生产环境建议关闭内置服务，改用外部托管服务。

```yaml
postgres:
  enabled: false
redis:
  enabled: false
rabbitmq:
  enabled: false
etcd:
  enabled: false
minio:
  enabled: false
milvus:
  enabled: false
```

关闭后，在 `backendConfig` 和 `secrets` 中填写外部服务地址和凭据。

### Ingress

启用 Ingress：

```yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: rag.yourcompany.com
      paths:
        - path: /
          pathType: Prefix
          service: kong
          port: 8000
  tls:
    - secretName: rag-tls
      hosts:
        - rag.yourcompany.com
```

### 自动扩缩容

`app-backend` 默认启用 HPA，基于 CPU/Memory 自动扩缩容：

```yaml
appBackend:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
```

## 生产部署建议

1. **替换所有默认密码和密钥**：特别是 `JWT_SECRET_KEY`、数据库密码、MinIO 密码。
2. **使用外部托管有状态服务**：RDS/Cloud SQL、ElastiCache/Redis Cloud、CloudAMQP、S3/MinIO 集群、Milvus 集群。
3. **配置 TLS**：通过 Ingress + cert-manager 自动管理证书。
4. **限制外网访问**：仅暴露 Kong 入口，管理面（Grafana、Prometheus、Kong Admin）不暴露公网或使用白名单。
5. **GPU 节点**：`embed-worker` 可向量化本地模型，需要 GPU node 时添加 `nodeSelector`/`tolerations`。
6. **持久化存储**：为所有 StatefulSet 配置可靠的 StorageClass 和备份策略。
7. **日志与监控**：接入集群级日志收集（Loki/EFK）和告警通道（Slack/PagerDuty）。

## 常用命令

```bash
# 渲染模板检查
helm template rag-system ./rag-system -f ./rag-system/values.yaml -f ./rag-system/secrets.yaml

# Chart 检查
helm lint ./rag-system

# 升级部署
bash upgrade.sh rag-system rag-system ./my-values.yaml

# 回滚
helm rollback rag-system <revision> -n rag-system

# 查看 Pod 日志
kubectl logs -n rag-system deployment/rag-system-app-backend
kubectl logs -n rag-system deployment/rag-system-ingest-worker

# 进入后端 Pod 调试
kubectl exec -it -n rag-system deployment/rag-system-app-backend -- bash
```

## 故障排查

### Pod 启动失败

```bash
kubectl describe pod -n rag-system <pod-name>
kubectl logs -n rag-system <pod-name>
```

### 数据库迁移失败

迁移以 Helm hook Job 形式运行：

```bash
kubectl logs -n rag-system job/rag-system-migrate
```

### MinIO bucket 未创建

```bash
kubectl logs -n rag-system job/rag-system-minio-init
```

### 前端无法访问后端

检查前端 nginx 配置挂载的 ConfigMap：

```bash
kubectl get configmap -n rag-system rag-system-nginx -o yaml
```

确认 `rag-system-app-backend` Service 存在且 Endpoint 正常：

```bash
kubectl get endpoints -n rag-system rag-system-app-backend
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `Chart.yaml` | Helm Chart 元数据 |
| `values.yaml` | 默认配置（内置有状态服务，适合开发） |
| `values-production.yaml` | 生产示例（关闭内置服务） |
| `secrets.yaml.example` | 密钥模板 |
| `generate-secrets.sh` | 从 `backend/.env` 生成 `secrets.yaml` |
| `upgrade.sh` | 安装/升级脚本 |
| `templates/` | K8s 资源模板 |
