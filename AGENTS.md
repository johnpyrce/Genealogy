# Repository guide

## Purpose and source of truth

This project reconciles genealogy charts.
Read `README.md` for the workflow and output details.
The editable CSV files in `data/registries/` are authoritative; trees,
analytics, exports, and dashboard data are derived from them.

- `people.csv` and `families.csv` define people and family relationships.
- `sources.csv`, `relationship_evidence.csv`, and `person_source_evidence.csv`
  record provenance and confidence. Original charts live in
  `data/source-material/charts/`.
- Preserve stable person IDs, Polish spelling and diacritics, source notes,
  unknown values, and alternative accounts. Do not infer missing facts or
  silently resolve conflicting parentage.
- Family IDs must remain sequential and match CSV row order. Reordering or
  inserting families requires keeping evidence references consistent.
- Keep evidence aligned with registry changes. Confidence values are
  `confirmed`, `probable`, and `uncertain`; branch roles are `main_line`,
  `spouse_ancestry`, and `collateral`.

## Code and output locations

- `scripts/`: Python validation, generation, analytics, and export modules.
  Reuse the shared registry loaders and paths in `scripts/lib/genealogy_data.py`.
- `scripts/templates/family_chart.html`: template for the family-chart viewer.
- `tests/`: standard-library `unittest` regression tests.
- `docs/`: working narrative, transcription, and history. The generated
  `docs/trees/merged_family_tree_box_drawing.md` should be regenerated through
  `scripts.build_box_drawing_tree`, not edited by hand.
- `apps/analytics-dashboard/`: React dashboard. Read its local `AGENTS.md`
  before editing; it defines authored content boundaries, protected runtime
  files, and the required build workflow. Correct underlying genealogy data
  in the registries and regenerate its reviewed snapshot through
  `scripts.sync_genealogy_analytics_dashboard`.
- `artifacts/`: ignored, reproducible reports, DuckDB database, GEDCOM, and
  interactive HTML. Dashboard build output and dependencies are also ignored.
- `archive/`: ignored historical material; do not treat it as authoritative.
  Preserve original charts and family photographs in `media/photos/`.

## Commands

Run from the repository root. Python requires 3.12 or newer; dependencies are
managed with `uv` via `pyproject.toml` and `uv.lock`.

```sh
# Validate registry references and evidence.
uv run python -m scripts.validate_genealogy_data

# Run all Python regression tests.
uv run python -m unittest discover -s tests

# Run focused suites.
uv run python -m unittest tests.test_genealogy_analytics
uv run python -m unittest tests.test_family_chart

# Regenerate all artifacts and build the dashboard.
./build_all.sh

# Rebuild analytics/dashboard and serve at http://127.0.0.1:4175/?view=1.
./refresh_dashboard.sh

# Generate only the standalone family-chart viewer.
uv run python -m scripts.build_family_chart
```

Both shell workflows currently reference an absolute, locally installed Data
plugin path. Check its availability before using them elsewhere and follow the
dashboard guide to resolve the installed builder. Do not replace the protected
runtime or install app dependencies merely to bypass a missing builder.
`refresh_dashboard.sh` starts a long-running HTTP server.

## Verification and change discipline

- Validate after registry changes and run the regression suites affected by
  code or data changes. Some analytical tests assert the current dataset's
  counts; update expectations only when justified by an intentional data change.
- Regenerate affected tracked outputs from their generators. Do not commit
  ignored artifacts, local caches, or dependencies.
- For viewer changes, verify relevant browser interactions as well as Python
  conversion tests. Family-chart generation is offline, but viewing uses
  pinned family-chart and D3 assets from a CDN.
- Follow existing Python module conventions: four-space indentation, explicit
  UTF-8 file handling, `pathlib` paths, and module entry points invoked with
  `python -m scripts.<module>`.
- Keep changes focused and report which checks ran and any unavailable checks.
