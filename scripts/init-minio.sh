#!/bin/sh
set -e

# 等待 MinIO 就绪后创建默认 bucket（保持私有）
mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb "local/${MINIO_BUCKET}" --ignore-existing

echo "MinIO bucket '${MINIO_BUCKET}' initialized."
