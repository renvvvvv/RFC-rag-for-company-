#!/usr/bin/env bash
#
# Rollback to the previously active color.
#
# Usage:
#   rollback.sh

set -euo pipefail

BASE_DIR="${DEPLOY_BASE_DIR:-/opt/rag-system}"
ACTIVE_FILE="$BASE_DIR/.active-color"

declare -A BACKEND_PORTS=( [blue]=8080 [green]=8081 )
declare -A FRONTEND_PORTS=( [blue]=3002 [green]=3003 )
declare -A KONG_PROXY_HTTP_PORTS=( [blue]=8000 [green]=8002 )

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

get_active_color() {
  if [ -f "$ACTIVE_FILE" ]; then
    cat "$ACTIVE_FILE"
  else
    echo "blue"
  fi
}

main() {
  local current new
  current="$(get_active_color)"
  if [ "$current" == "blue" ]; then
    new="green"
  else
    new="blue"
  fi

  log "Current active color: $current"
  log "Rolling back to: $new"

  cd "$BASE_DIR-$new" || { log "ERROR: $BASE_DIR-$new does not exist"; exit 1; }
  docker compose -f docker-compose.app.yml start || docker compose -f docker-compose.app.yml up -d

  echo "$new" > "$ACTIVE_FILE"

  cd "$BASE_DIR-$current" || exit 1
  docker compose -f docker-compose.app.yml stop || true

  log "Rollback complete. Active color: $new"
  log "Kong proxy: http://localhost:${KONG_PROXY_HTTP_PORTS[$new]}"
}

main
