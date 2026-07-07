#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"

echo "=== acoustic-comms-engine bootstrap ==="

# ── .env ─────────────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo "Created .env from .env.example"
    else
        echo "ERROR: No .env.example found at ${ENV_EXAMPLE}"
        exit 1
    fi
else
    echo ".env already exists — skipping"
fi

# ── Docker Compose Build ─────────────────────────────────────────────
echo "Building Docker images..."
docker compose -f "${ROOT_DIR}/infra/docker-compose.yml" build

# ── Start infrastructure services ────────────────────────────────────
echo "Starting infrastructure services (postgres, redis, qdrant, minio)..."
docker compose -f "${ROOT_DIR}/infra/docker-compose.yml" up -d \
    postgres redis qdrant minio

# ── Wait for healthy ─────────────────────────────────────────────────
echo "Waiting for services to become healthy..."

wait_for_healthy() {
    local service="$1"
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        local status
        status=$(docker compose -f "${ROOT_DIR}/infra/docker-compose.yml" ps --format json "$service" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health',''))" 2>/dev/null || echo "")
        if [ "$status" = "healthy" ]; then
            echo "  ✓ $service is healthy"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    echo "  ✗ $service did not become healthy within $((max_attempts * 2))s"
    return 1
}

wait_for_healthy postgres
wait_for_healthy redis

echo "All infrastructure services ready."

echo "Tables are auto-created on API startup (create_all)."

# ── Print URLs ──────────────────────────────────────────────────────
echo ""
echo "=== Services ==="
echo "  API:        http://localhost:8000"
echo "  Frontend:   http://localhost:3000  (start with 'docker compose up -d frontend')"
echo "  PostgreSQL: postgresql://postgres:postgres@localhost:5432/acoustic_comms"
echo "  PgBouncer:  postgresql://postgres:postgres@localhost:5433/acoustic_comms"
echo "  Redis:      redis://localhost:6379"
echo "  Qdrant:     http://localhost:6333"
echo "  MinIO:      http://localhost:9000 (console: http://localhost:9001)"
echo ""
echo "=== Getting started ==="
echo "  docker compose -f infra/docker-compose.yml up -d"
echo "  docker compose logs -f"
echo ""
echo "Bootstrap complete."
