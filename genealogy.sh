#!/bin/sh
set -eu
genealogy_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$genealogy_root"
exec uv run python -m scripts.genealogy "$@"
