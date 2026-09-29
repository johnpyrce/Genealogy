#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ "${1:-}" = "--build-only" ]; then
  shift
  exec ./build.sh site "$@"
fi
exec ./build.sh site --serve "$@"
