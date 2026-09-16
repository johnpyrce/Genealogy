#!/usr/bin/env sh
set -eu

uv run python -m scripts.build_genealogy_analytics
uv run python -m scripts.render_genealogy_analytics_report
uv run python -m scripts.sync_genealogy_analytics_dashboard
node /Users/johnpyrce/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.8/scripts/data-app.mjs build \
  --project-dir "$PWD/apps/analytics-dashboard" --separate-data
python3 -m http.server 4175 --bind 127.0.0.1 --directory apps/analytics-dashboard/dist
