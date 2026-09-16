#!/usr/bin/env sh
set -eu

uv run python -m scripts.validate_genealogy_data
uv run python -m scripts.build_box_drawing_tree
uv run python -m scripts.build_genealogy_analytics
uv run python -m scripts.render_genealogy_analytics_report
uv run python -m scripts.sync_genealogy_analytics_dashboard
uv run python -m scripts.export_gedcom
uv run python -m scripts.build_cytoscape_genealogy_graph
uv run python -m scripts.build_family_chart
node /Users/johnpyrce/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.8/scripts/data-app.mjs build \
  --project-dir "$PWD/apps/analytics-dashboard" --separate-data
