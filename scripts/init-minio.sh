#!/bin/sh
set -e

# 等待 MinIO 就绪后创建默认 bucket
mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb "local/${MINIO_BUCKET}" --ignore-existing
# 可选：将 bucket 设置为只读公开（根据安全策略调整）
mc anonymous set download "local/${MINIO_BUCKET}" || true

echo "MinIO bucket '${MINIO_BUCKET}' initialized."
