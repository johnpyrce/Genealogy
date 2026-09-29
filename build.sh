#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

usage() {
  printf 'Usage: %s [all | dashboard [--serve] | site [--serve [--port PORT]]]\n' "$0" >&2
  exit 2
}

build_dashboard() {
  uv run python -m scripts.build_genealogy_analytics
  uv run python -m scripts.render_genealogy_analytics_report
  uv run python -m scripts.sync_genealogy_analytics_dashboard
  uv run python -m scripts.build_dashboard
}

build_all() {
  uv run python -m scripts.validate_genealogy_data
  uv run python -m scripts.build_box_drawing_tree
  build_dashboard
  uv run python -m scripts.export_gedcom
  uv run python -m scripts.build_cytoscape_genealogy_graph
  uv run python -m scripts.build_family_chart
}

command=${1:-all}
if [ "$#" -gt 0 ]; then
  shift
fi

case "$command" in
  all)
    [ "$#" -eq 0 ] || usage
    build_all
    ;;
  dashboard)
    case "${1:-}" in
      '')
        build_dashboard
        ;;
      --serve)
        shift
        [ "$#" -eq 0 ] || usage
        build_dashboard
        exec python3 -m http.server 4175 --bind 127.0.0.1 --directory apps/analytics-dashboard/dist
        ;;
      *) usage ;;
    esac
    ;;
  site)
    case "${1:-}" in
      '') exec uv run python -m scripts.website build ;;
      --serve)
        shift
        exec uv run python -m scripts.website preview "$@"
        ;;
      *) usage ;;
    esac
    ;;
  *) usage ;;
esac
