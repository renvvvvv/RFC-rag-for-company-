#!/usr/bin/env bash
# =============================================================================
# Generate k8s/helm/rag-system/secrets.yaml from backend/.env
# Usage: bash k8s/helm/rag-system/generate-secrets.sh [path/to/.env]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-${SCRIPT_DIR}/../../../backend/.env}"
ENV_FILE="$(realpath -m "$ENV_FILE" 2>/dev/null || echo "$ENV_FILE")"
OUTPUT_FILE="${SCRIPT_DIR}/secrets.yaml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env file not found at $ENV_FILE" >&2
  exit 1
fi

echo "Generating ${OUTPUT_FILE} from ${ENV_FILE}..."

# Secrets to extract from .env
SECRETS=(
  POSTGRES_USER
  POSTGRES_PASSWORD
  DATABASE_URL
  REDIS_URL
  RABBITMQ_DEFAULT_USER
  RABBITMQ_DEFAULT_PASS
  RABBITMQ_URL
  MINIO_ROOT_USER
  MINIO_ROOT_PASSWORD
  MINIO_ACCESS_KEY
  MINIO_SECRET_KEY
  JWT_SECRET_KEY
  EMBEDDING_API_URL
  EMBEDDING_API_KEY
  RERANK_API_URL
  RERANK_API_KEY
  LLM_API_URL
  LLM_API_KEY
  MINIMAX_API_KEY
  GRAFANA_ADMIN_USER
  GRAFANA_ADMIN_PASSWORD
)

{
  echo "# Auto-generated from ${ENV_FILE}"
  echo "# WARNING: Do NOT commit this file to Git."
  echo "secrets:"

  for key in "${SECRETS[@]}"; do
    value=$(grep "^${key}=" "$ENV_FILE" 2>/dev/null | head -n1 | cut -d'=' -f2- || true)
    # If key is missing, use empty string
    echo "  ${key}: \"${value}\""
  done
} > "$OUTPUT_FILE"

echo "Done: ${OUTPUT_FILE}"
