#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

uv run python -m scripts.validate_genealogy_data
uv run python -m scripts.build_box_drawing_tree
uv run python -m scripts.build_genealogy_analytics
uv run python -m scripts.render_genealogy_analytics_report
uv run python -m scripts.sync_genealogy_analytics_dashboard
uv run python -m scripts.export_gedcom
uv run python -m scripts.build_cytoscape_genealogy_graph
uv run python -m scripts.build_family_chart
uv run python -m scripts.build_dashboard
