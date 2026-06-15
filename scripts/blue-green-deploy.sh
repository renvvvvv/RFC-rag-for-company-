#!/usr/bin/env bash
#
# Blue-green deployment script for the enterprise private RAG system.
#
# This script is designed to be safe for the target server:
#   - It does NOT install any system-wide software.
#   - It operates only inside BASE_DIR.
#   - It preserves backend/.env files.
#   - It leaves the previously active color intact until the new color passes
#     health checks, allowing instant rollback.
#
# Usage:
#   blue-green-deploy.sh [blue|green]
#
# If no color is given, the script automatically deploys to the inactive color.

set -euo pipefail

BASE_DIR="${DEPLOY_BASE_DIR:-/opt/rag-system}"
ACTIVE_FILE="$BASE_DIR/.active-color"
REPO_URL="${REPO_URL:-https://github.com/renvvvvv/RFC-rag-for-company-.git}"

# Registry credentials (optional). If provided, the script logs in before pulling.
REGISTRY_URL="${REGISTRY_URL:-}"
REGISTRY_USERNAME="${REGISTRY_USERNAME:-}"
REGISTRY_PASSWORD="${REGISTRY_PASSWORD:-}"

# Color-specific ports (fixed to avoid conflicts)
declare -A BACKEND_PORTS=( [blue]=8080 [green]=8081 )
declare -A FRONTEND_PORTS=( [blue]=3002 [green]=3003 )
declare -A KONG_PROXY_HTTP_PORTS=( [blue]=8000 [green]=8002 )
declare -A KONG_PROXY_HTTPS_PORTS=( [blue]=8443 [green]=8445 )
declare -A KONG_ADMIN_PORTS=( [blue]=8001 [green]=8003 )
declare -A KONG_ADMIN_HTTPS_PORTS=( [blue]=8444 [green]=8446 )

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    log "ERROR: Docker is not installed on this server."
    log "Please install Docker and the Docker Compose plugin, then re-run this script."
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    log "ERROR: Docker Compose plugin is not installed on this server."
    exit 1
  fi
}

get_active_color() {
  if [ -f "$ACTIVE_FILE" ]; then
    cat "$ACTIVE_FILE"
  else
    echo "blue"
  fi
}

clone_if_missing() {
  local dir="$1"
  if [ ! -d "$dir/.git" ]; then
    log "Cloning repository into $dir"
    git clone "$REPO_URL" "$dir"
  fi
}

pull_code() {
  local dir="$1"
  cd "$dir"
  log "Pulling latest code in $dir"
  git stash push -m "blue-green-auto-stash" || true
  git pull origin main
  git stash pop || true
}

protect_env() {
  local dir="$1"
  if [ ! -f "$dir/backend/.env" ]; then
    log "$dir/backend/.env not found, creating from template."
    cp "$dir/backend/.env.example" "$dir/backend/.env"
    log "WARNING: please edit $dir/backend/.env with real credentials."
  else
    log "$dir/backend/.env exists, preserving it."
  fi
}

start_infra() {
  cd "$BASE_DIR"
  if [ -f "docker-compose.infra.yml" ]; then
    log "Starting shared infrastructure (if not already running)"
    docker compose -f docker-compose.infra.yml up -d
  else
    log "WARNING: docker-compose.infra.yml not found in $BASE_DIR"
  fi
}

deploy_color() {
  local color="$1"
  local dir="$BASE_DIR-$color"

  log "=== Deploying color: $color ==="

  clone_if_missing "$dir"
  pull_code "$dir"
  protect_env "$dir"

  cd "$dir"

  export DEPLOY_COLOR="$color"
  export BACKEND_PORT="${BACKEND_PORTS[$color]}"
  export FRONTEND_PORT="${FRONTEND_PORTS[$color]}"
  export KONG_PROXY_HTTP_PORT="${KONG_PROXY_HTTP_PORTS[$color]}"
  export KONG_PROXY_HTTPS_PORT="${KONG_PROXY_HTTPS_PORTS[$color]}"
  export KONG_ADMIN_PORT="${KONG_ADMIN_PORTS[$color]}"
  export KONG_ADMIN_HTTPS_PORT="${KONG_ADMIN_HTTPS_PORTS[$color]}"

  if [ -n "$REGISTRY_URL" ] && [ -n "$REGISTRY_USERNAME" ] && [ -n "$REGISTRY_PASSWORD" ]; then
    log "Logging in to registry $REGISTRY_URL"
    echo "$REGISTRY_PASSWORD" | docker login "$REGISTRY_URL" -u "$REGISTRY_USERNAME" --password-stdin
  fi

  log "Pulling images for color $color"
  docker compose -f docker-compose.app.yml pull

  log "Starting color $color"
  docker compose -f docker-compose.app.yml up -d

  if [ -n "$REGISTRY_URL" ]; then
    docker logout "$REGISTRY_URL" || true
  fi

  # Health check
  log "Waiting for backend to be ready..."
  local attempts=0
  local max_attempts=30
  until docker compose -f docker-compose.app.yml exec -T app-backend curl -fsS http://localhost:8080/api/v1/health >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge "$max_attempts" ]; then
      log "ERROR: Health check failed for color $color after $max_attempts attempts."
      return 1
    fi
    sleep 2
  done

  log "Health check passed for color $color"
  return 0
}

stop_color() {
  local color="$1"
  local dir="$BASE_DIR-$color"
  if [ -d "$dir" ]; then
    log "Stopping color $color"
    cd "$dir"
    docker compose -f docker-compose.app.yml stop || true
  fi
}

switch_active() {
  local new_active="$1"
  log "Switching active color to $new_active"
  echo "$new_active" > "$ACTIVE_FILE"
}

print_access_info() {
  local color
  color="$(get_active_color)"
  log ""
  log "=================================================="
  log "Active color: $color"
  log "Kong proxy:   http://localhost:${KONG_PROXY_HTTP_PORTS[$color]}"
  log "Frontend:     http://localhost:${FRONTEND_PORTS[$color]}"
  log "Backend:      http://localhost:${BACKEND_PORTS[$color]}"
  log "=================================================="
}

main() {
  ensure_docker

  local requested_color="${1:-}"
  local active_color inactive_color

  active_color="$(get_active_color)"
  if [ -n "$requested_color" ]; then
    inactive_color="$requested_color"
  elif [ "$active_color" == "blue" ]; then
    inactive_color="green"
  else
    inactive_color="blue"
  fi

  log "Current active color: $active_color"
  log "Target color to deploy: $inactive_color"

  # Ensure infrastructure is running (shared)
  start_infra

  # Deploy to the inactive color
  if ! deploy_color "$inactive_color"; then
    log "ERROR: Deployment to $inactive_color failed."
    log "The active color ($active_color) is still running. No traffic was switched."
    exit 1
  fi

  # Switch active marker
  switch_active "$inactive_color"

  # Stop the old color after a short grace period
  log "Waiting 10 seconds before stopping old color..."
  sleep 10
  stop_color "$active_color"

  print_access_info
  log "Deployment complete."
}

main "$@"
