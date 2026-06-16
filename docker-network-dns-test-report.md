# Docker Compose 网络与 DNS 测试报告

生成时间: 2026-06-16T11:14:49+08:00

## 1. 网络拓扑

Compose 项目名（top-level name）: \rag-system\


### docker network inspect 摘要
```json
[
    {
        "Name": "rag-system_rag-network",
        "Id": "4e0c4fca1824574efd69e77893144d073e1c07b1b32b8020f1666d0af45e5c11",
        "Created": "2026-06-12T06:47:56.286416318Z",
        "Scope": "local",
        "Driver": "bridge",
        "EnableIPv4": true,
        "EnableIPv6": false,
        "IPAM": {
            "Driver": "default",
            "Options": null,
            "Config": [
                {
                    "Subnet": "172.24.0.0/16",
                    "Gateway": "172.24.0.1"
                }
            ]
        },
        "Internal": false,
        "Attachable": false,
        "Ingress": false,
        "ConfigFrom": {
            "Network": ""
        },
        "ConfigOnly": false,
        "Options": {
            "com.docker.network.enable_ipv4": "true",
            "com.docker.network.enable_ipv6": "false"
        },
        "Labels": {
            "com.docker.compose.config-hash": "f2d29929ce26bbfc6399a41837cca83de83c7435e8a9813e8906a816581c6ffb",
            "com.docker.compose.network": "rag-network",
            "com.docker.compose.project": "rag-system",
            "com.docker.compose.version": "5.1.1"
        },
        "Containers": {
            "0d1639567fcb8c068aaf75f914b63af505d2ffe9b4135007630180bab257999c": {
                "Name": "rag-redis",
                "EndpointID": "81d2fad6446d707d9819a8ed6606dc69b886a18bf3f58b682c1f8ba8d8bbcd4d",
                "MacAddress": "9e:b0:0f:f1:2e:27",
                "IPv4Address": "172.24.0.4/16",
                "IPv6Address": ""
            },
            "30dfef7b50b7ff2d64c8469665f44b6d657f4698c788db35986c9086b7ac647e": {
                "Name": "rag-rabbitmq",
                "EndpointID": "59a9de69cdea2bbff427a52700b88805b8acb06c3aa160efb682ecce2fae15ae",
                "MacAddress": "76:37:65:7f:ee:4f",
                "IPv4Address": "172.24.0.7/16",
                "IPv6Address": ""
            },
            "510241346a4853cd82ddd1b611808ed3f123fc1087002f54053dd7c57ec51eb3": {
                "Name": "rag-postgres",
                "EndpointID": "8c81b923788ca84268c1d304bd307001fe6bb3c13a4b02a36194294e73ff7931",
                "MacAddress": "6a:b1:fb:6a:18:98",
                "IPv4Address": "172.24.0.8/16",
                "IPv6Address": ""
            },
            "5690c7522431d37085c8118c813eabb34013052c90cbc121af2acdc4fb1f44d4": {
                "Name": "rag-app-backend",
                "EndpointID": "bf898202b7b471e267fb4d992188d8e3d1d058eb6dc788ef2906bea8bb11e0ec",
                "MacAddress": "ea:ab:c7:14:7c:f3",
                "IPv4Address": "172.24.0.13/16",
                "IPv6Address": ""
            },
            "677e90065291a70a7c5da3719b47edc665f93f59dfca9bae1d449ddea110a9d3": {
                "Name": "rag-minio",
                "EndpointID": "2569da0524443d31679d80f1a238e80305c6157964d2f5231d8933676ba85007",
                "MacAddress": "0a:25:3a:76:4d:de",
                "IPv4Address": "172.24.0.5/16",
                "IPv6Address": ""
            },
            "7c63f0abf0c9bb0529b28dcb1fb400bc6f4dc170ea35e2f823a7fb7130a8847a": {
                "Name": "rag-embed-worker",
                "EndpointID": "68ef82fb95ebe7827923bb7d90a8df3411c44b4983997d7bccd1afb85dd7724d",
                "MacAddress": "c2:93:26:c6:22:e1",
                "IPv4Address": "172.24.0.11/16",
                "IPv6Address": ""
            },
            "840bd15b5b08f60f2ed03b9dbee170fc937efd6a1f04f3d29b47da385b158d6c": {
                "Name": "rag-etcd",
                "EndpointID": "5bfc6e9bf27f926d9a17394067408f863a3a4581cce0ac932b26ffaca6c00ba0",
                "MacAddress": "d2:d2:5b:12:1f:d0",
                "IPv4Address": "172.24.0.2/16",
                "IPv6Address": ""
            },
            "903e3a9e6ebe3f19d6ae9560be9f568da7e5586c30c78d95b9fed55588e9534a": {
                "Name": "rag-prometheus",
                "EndpointID": "23094ac632f0bf304cc20caaf1678044a989f3fc39df602cd80c54591e125bdf",
                "MacAddress": "0a:dd:21:96:38:4e",
                "IPv4Address": "172.24.0.6/16",
                "IPv6Address": ""
            },
            "c77d89553fc3cc0ee46f24d0064912cdd4700e3a5024e275d1695ea88f054194": {
                "Name": "rag-milvus",
                "EndpointID": "77797dbf67c00b5b5819417cac9d3084af526b2498e840ea0bd63d74654ca2d6",
                "MacAddress": "42:08:8d:dd:4f:cb",
                "IPv4Address": "172.24.0.10/16",
                "IPv6Address": ""
            },
            "cd363157da02d22f9fe1049812d4a4fa5ee4d2c0b4f5c41bbc956c9847103c21": {
                "Name": "rag-frontend",
                "EndpointID": "07446d3e82663d0d24e034fa0cbb0b51f5750786260cd00c6510ad1abc6e23d4",
                "MacAddress": "8e:dc:79:94:1b:ff",
                "IPv4Address": "172.24.0.14/16",
                "IPv6Address": ""
            },
            "ceba9a0c7234bc2d61f84f847f44e04bf009717668c3db78c8b1ca1a89a12aa3": {
                "Name": "rag-permission-sync-worker",
                "EndpointID": "7a8bbce97e2d587f53aa18e556760815cafe61f254dedf96a01797570154f32d",
                "MacAddress": "a2:f2:ad:37:65:e8",
                "IPv4Address": "172.24.0.3/16",
                "IPv6Address": ""
            },
            "d4bfa238fd6b3459ab979363721a68156e123e7e69c091f2fcafeff0500b5082": {
                "Name": "rag-ingest-worker",
                "EndpointID": "137587ca1a8347e09ad777a9c4aa9f9e977a54a56b8ecf8b1a5703cd7ca7881a",
                "MacAddress": "de:da:1e:dd:eb:20",
                "IPv4Address": "172.24.0.12/16",
                "IPv6Address": ""
```

### 同网段容器与 IP

| 容器名 | IPv4 地址 |
|--------|-----------|

| rag-app-backend | 172.24.0.13/16 |
| rag-embed-worker | 172.24.0.11/16 |
| rag-etcd | 172.24.0.2/16 |
| rag-frontend | 172.24.0.14/16 |
| rag-grafana | 172.24.0.9/16 |
| rag-ingest-worker | 172.24.0.12/16 |
| rag-kong | 172.24.0.15/16 |
| rag-milvus | 172.24.0.10/16 |
| rag-minio | 172.24.0.5/16 |
| rag-permission-sync-worker | 172.24.0.3/16 |
| rag-postgres | 172.24.0.8/16 |
| rag-prometheus | 172.24.0.6/16 |
| rag-rabbitmq | 172.24.0.7/16 |
| rag-redis | 172.24.0.4/16 |

## 2. DNS 解析结果（Ping 测试）

> 说明：为便于测试，已在 app-backend、rag-kong 中临时安装 iputils-ping / netcat-openbsd。

### 2.1 从 app-backend ping 依赖服务

#### rag-app-backend -> postgres
```
PING postgres (172.24.0.8) 56(84) bytes of data.
64 bytes from rag-postgres.rag-system_rag-network (172.24.0.8): icmp_seq=1 ttl=64 time=0.346 ms
64 bytes from rag-postgres.rag-system_rag-network (172.24.0.8): icmp_seq=2 ttl=64 time=0.103 ms

--- postgres ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1001ms
rtt min/avg/max/mdev = 0.103/0.224/0.346/0.121 ms
```
#### rag-app-backend -> redis
```
PING redis (172.24.0.4) 56(84) bytes of data.
64 bytes from rag-redis.rag-system_rag-network (172.24.0.4): icmp_seq=1 ttl=64 time=0.385 ms
64 bytes from rag-redis.rag-system_rag-network (172.24.0.4): icmp_seq=2 ttl=64 time=0.181 ms

--- redis ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1007ms
rtt min/avg/max/mdev = 0.181/0.283/0.385/0.102 ms
```
#### rag-app-backend -> milvus-standalone
```
PING milvus-standalone (172.24.0.10) 56(84) bytes of data.
64 bytes from rag-milvus.rag-system_rag-network (172.24.0.10): icmp_seq=1 ttl=64 time=0.267 ms
64 bytes from rag-milvus.rag-system_rag-network (172.24.0.10): icmp_seq=2 ttl=64 time=0.112 ms

--- milvus-standalone ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1006ms
rtt min/avg/max/mdev = 0.112/0.189/0.267/0.077 ms
```
#### rag-app-backend -> rabbitmq
```
PING rabbitmq (172.24.0.7) 56(84) bytes of data.
64 bytes from rag-rabbitmq.rag-system_rag-network (172.24.0.7): icmp_seq=1 ttl=64 time=0.336 ms
64 bytes from rag-rabbitmq.rag-system_rag-network (172.24.0.7): icmp_seq=2 ttl=64 time=0.108 ms

--- rabbitmq ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1032ms
rtt min/avg/max/mdev = 0.108/0.222/0.336/0.114 ms
```
#### rag-app-backend -> minio
```
PING minio (172.24.0.5) 56(84) bytes of data.
64 bytes from rag-minio.rag-system_rag-network (172.24.0.5): icmp_seq=1 ttl=64 time=0.325 ms
64 bytes from rag-minio.rag-system_rag-network (172.24.0.5): icmp_seq=2 ttl=64 time=0.105 ms

--- minio ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1001ms
rtt min/avg/max/mdev = 0.105/0.215/0.325/0.110 ms
```
#### rag-app-backend -> kong
```
PING kong (172.24.0.15) 56(84) bytes of data.
64 bytes from rag-kong.rag-system_rag-network (172.24.0.15): icmp_seq=1 ttl=64 time=0.345 ms
64 bytes from rag-kong.rag-system_rag-network (172.24.0.15): icmp_seq=2 ttl=64 time=0.166 ms

--- kong ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1025ms
rtt min/avg/max/mdev = 0.166/0.255/0.345/0.089 ms
```
#### rag-app-backend -> frontend
```
PING frontend (172.24.0.14) 56(84) bytes of data.
64 bytes from rag-frontend.rag-system_rag-network (172.24.0.14): icmp_seq=1 ttl=64 time=0.652 ms
64 bytes from rag-frontend.rag-system_rag-network (172.24.0.14): icmp_seq=2 ttl=64 time=0.173 ms

--- frontend ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1001ms
rtt min/avg/max/mdev = 0.173/0.412/0.652/0.239 ms
```
#### rag-app-backend -> rag-milvus（容器名别名）
```
PING rag-milvus (172.24.0.10) 56(84) bytes of data.
64 bytes from rag-milvus.rag-system_rag-network (172.24.0.10): icmp_seq=1 ttl=64 time=0.148 ms
64 bytes from rag-milvus.rag-system_rag-network (172.24.0.10): icmp_seq=2 ttl=64 time=0.105 ms

--- rag-milvus ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1011ms
rtt min/avg/max/mdev = 0.105/0.126/0.148/0.021 ms
```

### 2.2 从 app-frontend ping

#### rag-frontend -> app-backend
```
PING app-backend (172.24.0.13): 56 data bytes
64 bytes from 172.24.0.13: seq=0 ttl=64 time=0.240 ms
64 bytes from 172.24.0.13: seq=1 ttl=64 time=0.149 ms

--- app-backend ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.149/0.194/0.240 ms
```
#### rag-frontend -> kong
```
PING kong (172.24.0.15): 56 data bytes
64 bytes from 172.24.0.15: seq=0 ttl=64 time=0.170 ms
64 bytes from 172.24.0.15: seq=1 ttl=64 time=0.163 ms

--- kong ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.163/0.166/0.170 ms
```
### 2.3 从 kong ping

#### rag-kong -> app-backend
```
PING app-backend (172.24.0.13) 56(84) bytes of data.
64 bytes from rag-app-backend.rag-system_rag-network (172.24.0.13): icmp_seq=1 ttl=64 time=0.125 ms
64 bytes from rag-app-backend.rag-system_rag-network (172.24.0.13): icmp_seq=2 ttl=64 time=0.096 ms

--- app-backend ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1001ms
rtt min/avg/max/mdev = 0.096/0.110/0.125/0.014 ms
```
#### rag-kong -> frontend
```
PING frontend (172.24.0.14) 56(84) bytes of data.
64 bytes from rag-frontend.rag-system_rag-network (172.24.0.14): icmp_seq=1 ttl=64 time=0.093 ms
64 bytes from rag-frontend.rag-system_rag-network (172.24.0.14): icmp_seq=2 ttl=64 time=0.118 ms

--- frontend ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1035ms
rtt min/avg/max/mdev = 0.093/0.105/0.118/0.012 ms
```
## 3. /etc/resolv.conf DNS 配置

#### rag-app-backend /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-frontend /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-kong /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-postgres /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-redis /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-rabbitmq /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-milvus /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-minio /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-etcd /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-grafana /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-prometheus /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-ingest-worker /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-embed-worker /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
#### rag-permission-sync-worker /etc/resolv.conf
```
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```
## 4. 端口连通性（nc -zv）

### 4.1 从 app-backend

#### rag-app-backend -> app-backend:8080
```
Connection to app-backend (172.24.0.13) 8080 port [tcp/http-alt] succeeded!
```
#### rag-app-backend -> postgres:5432
```
Connection to postgres (172.24.0.8) 5432 port [tcp/postgresql] succeeded!
```
#### rag-app-backend -> redis:6379
```
Connection to redis (172.24.0.4) 6379 port [tcp/redis] succeeded!
```
#### rag-app-backend -> rabbitmq:5672
```
Connection to rabbitmq (172.24.0.7) 5672 port [tcp/amqp] succeeded!
```
#### rag-app-backend -> milvus-standalone:19530
```
Connection to milvus-standalone (172.24.0.10) 19530 port [tcp/*] succeeded!
```
#### rag-app-backend -> minio:9000
```
Connection to minio (172.24.0.5) 9000 port [tcp/*] succeeded!
```
#### rag-app-backend -> kong:8000
```
Connection to kong (172.24.0.15) 8000 port [tcp/*] succeeded!
```
#### rag-app-backend -> frontend:80
```
Connection to frontend (172.24.0.14) 80 port [tcp/http] succeeded!
```
### 4.2 从 app-frontend

#### rag-frontend -> app-backend:8080
```
app-backend (172.24.0.13:8080) open
```
#### rag-frontend -> kong:8000
```
kong (172.24.0.15:8000) open
```
### 4.3 从 kong

#### rag-kong -> app-backend:8080
```
Connection to app-backend (172.24.0.13) 8080 port [tcp/*] succeeded!
```
#### rag-kong -> frontend:80
```
Connection to frontend (172.24.0.14) 80 port [tcp/*] succeeded!
```
## 5. 容器健康与重启状态

| 容器 | 状态 | Health | Restarting | RestartCount |
|------|------|--------|------------|--------------|
| /rag-kong | running | healthy | false | 0 |
| /rag-app-backend | running | healthy | false | 0 |
| /rag-frontend | running | healthy | false | 0 |
| /rag-postgres | running | healthy | false | 0 |
| /rag-redis | running | healthy | false | 0 |
| /rag-rabbitmq | running | healthy | false | 0 |
| /rag-milvus | running | healthy | false | 0 |
| /rag-minio | running | healthy | false | 0 |
| /rag-etcd | running | healthy | false | 0 |
| /rag-grafana | running | healthy | false | 0 |
| /rag-prometheus | running | healthy | false | 0 |
| /rag-ingest-worker | running | n/a | false | 0 |
| /rag-embed-worker | running | n/a | false | 0 |
| /rag-permission-sync-worker | running | n/a | false | 0 |
| /rag-alertmanager | exited | unhealthy | false | 0 |
| /rag-minio-init | exited | n/a | false | 0 |

## 6. docker-compose.yml 网络/依赖/link 配置摘要

### networks
```yaml
networks:
  rag-network:
    driver: bridge
```

### depends_on 与 links（所有显式定义）
```yaml
      - rag-network
    depends_on:
      app-backend:
        condition: service_healthy
      frontend:
--
      - ./backend/.env:/app/.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
--
      MILVUS_PORT: ${MILVUS_PORT:-19530}
    depends_on:
      rabbitmq:
        condition: service_healthy
      postgres:
--
    # TODO: 私有化 GPU 环境启用 nvidia 运行时后，可添加 deploy.resources.reservations.devices
    depends_on:
      rabbitmq:
        condition: service_healthy
      milvus-standalone:
--
      RABBITMQ_URL: ${RABBITMQ_URL:-amqp://guest:guest@rabbitmq:5672/}
    depends_on:
      rabbitmq:
        condition: service_healthy
      postgres:
--
      - "3002:80"
    depends_on:
      app-backend:
        condition: service_healthy
    networks:
--
      - rag-network
    depends_on:
      etcd:
        condition: service_healthy
      minio:
--
      - rag-network
    depends_on:
      minio:
        condition: service_healthy
    restart: on-failure
--
      - rag-network
    depends_on:
      - prometheus
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:3000/api/health || exit 1"]
```

> 观察：当前 docker-compose.yml 中**没有使用 links**，所有服务通过共享网络 \rag-network\ 实现 DNS 互访。

