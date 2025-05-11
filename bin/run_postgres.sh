#!/usr/bin/env bash

podman rm -f recordings-db 2>/dev/null || true


podman run --name recordings-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=recordings \
  -p 5432:5432 \
  -v "$(pwd)/bin/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql:Z" \
  -d docker.io/library/postgres:latest


# PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d recordings
