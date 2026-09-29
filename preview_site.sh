#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ "${1:-}" = "--build-only" ]; then
  shift
  exec uv run python -m scripts.website build "$@"
fi
exec uv run python -m scripts.website preview "$@"
