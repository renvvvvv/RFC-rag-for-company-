#!/usr/bin/env bash
# Convenience wrapper to run the Locust load test headless against the local stack.
# Usage:
#   bash scripts/perf/run.sh
#   RAG_USERS=100 RAG_DURATION=120s bash scripts/perf/run.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

RAG_HOST="${RAG_HOST:-http://localhost:8080}"
RAG_USERS="${RAG_USERS:-50}"
RAG_SPAWN_RATE="${RAG_SPAWN_RATE:-5}"
RAG_DURATION="${RAG_DURATION:-60}"
RAG_ADMIN_USER="${RAG_ADMIN_USER:-admin}"
RAG_ADMIN_PASS="${RAG_ADMIN_PASS:-admin123}"

# Use the dedicated perf venv if it exists; otherwise fall back to a global locust.
if [ -f "${SCRIPT_DIR}/.venv/Scripts/python.exe" ]; then
    PYTHON="${SCRIPT_DIR}/.venv/Scripts/python.exe"
elif [ -f "${SCRIPT_DIR}/.venv/bin/python" ]; then
    PYTHON="${SCRIPT_DIR}/.venv/bin/python"
else
    echo "[WARN] Dedicated venv not found; trying system python + locust"
    PYTHON="python"
fi

export RAG_HOST RAG_USERS RAG_SPAWN_RATE RAG_DURATION RAG_ADMIN_USER RAG_ADMIN_PASS

echo "Starting Locust load test"
echo "  host       : ${RAG_HOST}"
echo "  users      : ${RAG_USERS}"
echo "  spawn rate : ${RAG_SPAWN_RATE}/s"
echo "  duration   : ${RAG_DURATION}"

"${PYTHON}" "${SCRIPT_DIR}/run_load_test.py" \
    --host "${RAG_HOST}" \
    -u "${RAG_USERS}" \
    -r "${RAG_SPAWN_RATE}" \
    -t "${RAG_DURATION}"

echo "Load test complete. Results written to ${SCRIPT_DIR}/results/"
