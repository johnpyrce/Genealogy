#!/usr/bin/env sh
set -eu
umask 077
cd "$(dirname "$0")"

usage() {
  cat <<'EOF'
Usage: ./visit_report.sh [--export] [--no-open]

Generate the full-history visitor notebook and HTML report, then open the HTML
in your default browser. Uses the saved local DuckDB archive by default.

  --export   First archive new online events and remove their verified online
             copies, using .env.visitor-access or the owner credential environment.
  --no-open  Generate the report without opening a browser.
  --help     Show this help.

Output: artifacts/visitor-access/visit_analysis.html
EOF
}

export_visits=0
open_report=1
for argument in "$@"; do
  case "$argument" in
    --export) export_visits=1 ;;
    --no-open) open_report=0 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$argument" >&2; usage >&2; exit 2 ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  printf 'uv is required. Install it before running this script.\n' >&2
  exit 1
fi

database=${VISITOR_ARCHIVE:-artifacts/visitor-access/visits.duckdb}
if [ "$export_visits" -eq 1 ]; then
  if [ -f .env.visitor-access ]; then
    uv run python -m scripts.visitor_access --env-file .env.visitor-access export --database "$database"
  else
    uv run python -m scripts.visitor_access export --database "$database"
  fi
fi

if [ ! -f "$database" ]; then
  printf 'Visitor archive not found. Run ./visit_report.sh --export first.\n' >&2
  exit 1
fi

printf 'Generating the visitor notebook and report from the full local archive...\n'
uv run --with matplotlib --with nbformat --with nbclient --with nbconvert --with ipykernel \
  python -m jupyter nbconvert --execute --to notebook \
  --ExecutePreprocessor.timeout=180 \
  --output visit_analysis --output-dir artifacts/visitor-access \
  scripts/templates/visit_analysis.ipynb

uv run --with nbconvert python -m jupyter nbconvert --to html --no-input \
  artifacts/visitor-access/visit_analysis.ipynb

report="$(pwd)/artifacts/visitor-access/visit_analysis.html"
printf 'Report ready: %s\n' "$report"
if [ "$open_report" -eq 1 ]; then
  case "$(uname -s)" in
    Darwin) open "$report" ;;
    *)
      if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$report"
      else
        uv run python -c 'import pathlib, sys, webbrowser; sys.exit(0 if webbrowser.open(pathlib.Path(sys.argv[1]).as_uri()) else 1)' "$report"
      fi
      ;;
  esac
fi
