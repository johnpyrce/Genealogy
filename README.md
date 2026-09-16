# Combined Muszyna genealogy

This repository reconciles six supplied genealogy charts for the Gościński,
Miczulski, Pyrc, and Rams families. The editable CSV registries are the source
of truth; every tree, export, analytics result, and dashboard is regenerated
from them.

## Repository layout

- `data/registries/` — editable people, family, source, and relationship-evidence CSV registries.
- `data/source-material/charts/` — the six original chart images cited by the source registry.
- `docs/` — chart transcription, historical notes, working sections, and the generated box-drawing tree.
- `media/photos/` — family photographs.
- `scripts/` — validation, generation, analytics, export, and dashboard-sync modules; `scripts/lib/` contains shared loaders.
- `tests/` — regression tests for the analytical layer and CSV-generated tree.
- `apps/analytics-dashboard/` — the interactive HTML analytics dashboard source.
- `artifacts/` — ignored, reproducible local outputs: DuckDB, reports, GEDCOM, and the interactive relationship graph.
- `archive/` — ignored local historical material retained pending review.

## Core commands

Validate the registries:

```sh
uv run python -m scripts.validate_genealogy_data
```

Rebuild every generated artifact and the dashboard bundle:

```sh
./build_all.sh
```

Refresh analytics and launch the local dashboard server:

```sh
./refresh_dashboard.sh
```

Then open `http://127.0.0.1:4175/?view=1`.

## Analytics workflow

`scripts.build_genealogy_analytics` recreates
`artifacts/analytics/genealogy_analytics.duckdb` and its reviewable JSON
catalog. `scripts.render_genealogy_analytics_report` renders the standalone
Markdown report, while `scripts.sync_genealogy_analytics_dashboard` updates
the dashboard’s reviewed data snapshot.

Run regression tests with:

```sh
uv run python -m unittest tests.test_genealogy_analytics
```

## Other generated artifacts

- `scripts.build_box_drawing_tree` writes `docs/trees/merged_family_tree_box_drawing.md`.
- `scripts.export_gedcom` writes the GEDCOM export under `artifacts/exports/`.
- `scripts.build_cytoscape_genealogy_graph` writes the interactive graph under `artifacts/interactive/`.

