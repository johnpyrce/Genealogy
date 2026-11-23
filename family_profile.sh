#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
exec uv run python -m scripts.build_family_profile --open "$@"
