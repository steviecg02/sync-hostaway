#!/bin/bash
set -e

log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S")] $*"
}

log "Running database migrations..."
alembic upgrade head

log "Starting application..."
exec "$@"
