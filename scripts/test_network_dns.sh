#!/usr/bin/env bash
# Docker network & DNS test script for rag-system
set -o pipefail

PROJECT_DIR="/c/Users/wuton/Desktop/企业级私有rag"
REPORT="${PROJECT_DIR}/docker-network-dns-test-report.md"
NETWORK="rag-system_rag-network"

# Containers as currently running (service vs container name)
BACKEND="rag-app-backend"
FRONTEND="rag-frontend"
KONG="rag-kong"

# Helper to run a command inside a container and capture output
run_in() {
  local container="$1"
  shift
  docker exec "$container" sh -c "$*" 2>&1
}

# Helper: ping test
ping_test() {
  local src="$1" target="$2"
  echo "#### ${src} -> ${target}"
  echo '```'
  run_in "$src" "ping -c 2 -W 2 '$target'" || true
  echo '```'
}

# Helper: nc port test
port_test() {
  local src="$1" target="$2" port="$3"
  echo "#### ${src} -> ${target}:${port}"
  echo '```'
  run_in "$src" "nc -zv -w 3 '$target' $port" || true
  echo '```'
}

# Helper: resolv.conf
dns_conf() {
  local container="$1"
  echo "#### ${container} /etc/resolv.conf"
  echo '```'
  run_in "$container" "cat /etc/resolv.conf" || true
  echo '```'
}

{
echo "# Docker Compose 网络与 DNS 测试报告"
echo ""
echo "生成时间: $(date -Iseconds)"
echo ""

echo "## 1. 网络拓扑"
echo ""
echo "Compose 项目名（top-level name）: \\"rag-system\\""
echo ""
echo "实际网络名: \\"${NETWORK}\\"（注意：不是 \\"rag-network\\"，因为 docker-compose.yml 中 networks.rag-network 没有指定 name，Docker Compose 自动命名为 \\"<project>_<network>\\"）"
echo ""
echo "### docker network inspect 摘要"
echo '```json'
docker network inspect "$NETWORK" | sed -n '1,120p'
echo '```'
echo ""

echo "### 同网段容器与 IP"
echo ""
echo "| 容器名 | IPv4 地址 |"
echo "|--------|-----------|"
docker network inspect "$NETWORK" -f '{{range $id, $c := .Containers}}{{printf "| %s | %s |\n" $c.Name $c.IPv4Address}}{{end}}' | sort
echo ""

echo "## 2. DNS 解析结果（Ping 测试）"
echo ""
echo "> 说明：为便于测试，已在 app-backend、rag-kong 中临时安装 iputils-ping / netcat-openbsd。"
echo ""

echo "### 2.1 从 app-backend ping 依赖服务"
echo ""
for target in postgres redis milvus-standalone rabbitmq minio kong frontend; do
  ping_test "$BACKEND" "$target"
done
# 额外验证容器名/别名
echo "#### ${BACKEND} -> rag-milvus（容器名别名）"
echo '```'
run_in "$BACKEND" "ping -c 2 -W 2 rag-milvus" || true
echo '```'
echo ""

echo "### 2.2 从 app-frontend ping"
echo ""
for target in app-backend kong; do
  ping_test "$FRONTEND" "$target"
done

echo "### 2.3 从 kong ping"
echo ""
for target in app-backend frontend; do
  ping_test "$KONG" "$target"
done

echo "## 3. /etc/resolv.conf DNS 配置"
echo ""
for c in rag-app-backend rag-frontend rag-kong rag-postgres rag-redis rag-rabbitmq rag-milvus rag-minio rag-etcd rag-grafana rag-prometheus rag-ingest-worker rag-embed-worker rag-permission-sync-worker; do
  dns_conf "$c"
done

echo "## 4. 端口连通性（nc -zv）"
echo ""
echo "### 4.1 从 app-backend"
echo ""
port_test "$BACKEND" app-backend 8080
port_test "$BACKEND" postgres 5432
port_test "$BACKEND" redis 6379
port_test "$BACKEND" rabbitmq 5672
port_test "$BACKEND" milvus-standalone 19530
port_test "$BACKEND" minio 9000
port_test "$BACKEND" kong 8000
port_test "$BACKEND" frontend 80

echo "### 4.2 从 app-frontend"
echo ""
port_test "$FRONTEND" app-backend 8080
port_test "$FRONTEND" kong 8000

echo "### 4.3 从 kong"
echo ""
port_test "$KONG" app-backend 8080
port_test "$KONG" frontend 80

echo "## 5. 容器健康与重启状态"
echo ""
echo "| 容器 | 状态 | Health | Restarting | RestartCount |"
echo "|------|------|--------|------------|--------------|"
for c in rag-kong rag-app-backend rag-frontend rag-postgres rag-redis rag-rabbitmq rag-milvus rag-minio rag-etcd rag-grafana rag-prometheus rag-ingest-worker rag-embed-worker rag-permission-sync-worker rag-alertmanager rag-minio-init; do
  docker inspect "$c" -f "| {{.Name}} | {{.State.Status}} | {{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}} | {{.State.Restarting}} | {{.RestartCount}} |" 2>/dev/null || echo "| $c | 不存在/未运行 | - | - | - |"
done
echo ""

echo "## 6. docker-compose.yml 网络/依赖/link 配置摘要"
echo ""
echo "### networks"
echo '```yaml'
grep -A2 '^networks:' "${PROJECT_DIR}/docker-compose.yml"
echo '```'
echo ""
echo "### depends_on 与 links（所有显式定义）"
echo '```yaml'
grep -B1 -A3 'depends_on:\|links:' "${PROJECT_DIR}/docker-compose.yml" | head -n 120
echo '```'
echo ""
echo "> 观察：当前 docker-compose.yml 中**没有使用 links**，所有服务通过共享网络 \\"rag-network\\" 实现 DNS 互访。"
echo ""
} > "$REPORT"

echo "报告已写入: $REPORT"
