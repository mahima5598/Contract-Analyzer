#!/usr/bin/env bash
set -euo pipefail

# Create necessary directories if they don't exist
mkdir -p /app/uploads /app/extracted /app/logs

# Execute the command passed from docker-compose
exec "$@"