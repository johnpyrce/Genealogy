#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

uv run python -m scripts.build_genealogy_analytics
uv run python -m scripts.render_genealogy_analytics_report
uv run python -m scripts.sync_genealogy_analytics_dashboard
uv run python -m scripts.build_dashboard
python3 -m http.server 4175 --bind 127.0.0.1 --directory apps/analytics-dashboard/dist
