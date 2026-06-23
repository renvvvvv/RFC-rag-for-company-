#!/usr/bin/env bash
# =============================================================================
# Helper script to install/upgrade the RAG system Helm release.
# Usage: bash upgrade.sh [release-name] [namespace] [values-files...]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_NAME="${1:-rag-system}"
NAMESPACE="${2:-rag-system}"
shift_count=$(( $# >= 2 ? 2 : $# ))
shift "$shift_count" 2>/dev/null || true
VALUES_ARGS=()

# Default values file
VALUES_ARGS+=("-f" "${SCRIPT_DIR}/values.yaml")

# Append any extra values files provided by the user
for file in "$@"; do
  VALUES_ARGS+=("-f" "$file")
done

# If secrets.yaml exists, include it automatically
if [[ -f "${SCRIPT_DIR}/secrets.yaml" ]]; then
  VALUES_ARGS+=("-f" "${SCRIPT_DIR}/secrets.yaml")
fi

echo "==> Upgrading release '${RELEASE_NAME}' in namespace '${NAMESPACE}'"
echo "    helm upgrade --install ${RELEASE_NAME} ${SCRIPT_DIR} \"
  -n ${NAMESPACE} --create-namespace \"
  "${VALUES_ARGS[@]}"

helm upgrade --install "${RELEASE_NAME}" "${SCRIPT_DIR}" \
  -n "${NAMESPACE}" \
  --create-namespace \
  "${VALUES_ARGS[@]}"

echo "==> Deployment status"
kubectl get pods -n "${NAMESPACE}"
