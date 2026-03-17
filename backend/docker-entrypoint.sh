#!/usr/bin/env bash
set -euo pipefail

# Optional environment setup
: "${LOG_DIR:=/app/logs}"
mkdir -p "$LOG_DIR"

# Allow passing a command to run
if [ $# -eq 0 ]; then
  echo "No command supplied. Exiting."
  exit 1
fi

# Exec the provided command so signals are forwarded correctly
exec "$@"
