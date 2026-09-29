# Combined Muszyna genealogy

This repository reconciles genealogy charts and creates CSV files with the
information from the charts.
The editable CSV registries are the source
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

## Build and preview

Run these commands from the repository root. Python 3.12 or newer is required;
dependencies are managed with `uv` using `pyproject.toml` and `uv.lock`.

| When you want to… | Command | Result |
| --- | --- | --- |
| Rebuild after changing registries or genealogy generation code | `./build.sh` | Validates registries and regenerates the tree, analytics, dashboard, GEDCOM, and interactive outputs. |
| Work on dashboard data or presentation | `./build.sh dashboard --serve` | Rebuilds analytics and the dashboard, then serves it at `http://127.0.0.1:4175/?view=1`. |
| Work on website content, layout, or photos | `./build.sh site --serve` | Runs the full build, builds the website, checks its internal links, then serves it at `http://127.0.0.1:4176/`. |

Omit `--serve` to build without starting a server: `./build.sh dashboard` or
`./build.sh site`. The site command **already runs the full build**, so there
is no need to run `./build.sh` immediately before it. Use `--port 4177` after
`site --serve` to choose another preview port.

The older commands remain available as wrappers: `./build_all.sh` is equivalent
to `./build.sh`, `./refresh_dashboard.sh` to `./build.sh dashboard --serve`, and
`./preview_site.sh` to `./build.sh site --serve`. The existing
`./preview_site.sh --build-only` builds the site without starting a server.

## Editing the registries manually

The CSV files in `data/registries/` are the source of truth. Edit them directly
when adding or correcting a person, family, or source account; generated trees,
dashboard data, and exports should be rebuilt from those files.

1. Check the original charts in `data/source-material/charts/` and the existing
   source notes before changing a fact. Keep Polish spelling and diacritics,
   unknown values, and conflicting accounts. Do not fill gaps by inference.
2. Edit `people.csv` for person details and `families.csv` for relationships.
   Keep existing person IDs stable. In `families.csv`, keep family IDs sequential
   and equal to their row order; `children_ids` uses semicolons between IDs.
3. Edit `sources.csv`, `relationship_evidence.csv`, and
   `person_source_evidence.csv` to keep citations and confidence aligned with
   the changes. If family rows move, update their evidence references.
   Confidence values are `confirmed`, `probable`, or `uncertain`; family branch
   roles are `main_line`, `spouse_ancestry`, or `collateral`.
4. Save the files as UTF-8 CSV, preserving headers, columns, and notes. Then
   rebuild (which validates the registries) and run the regression tests:

   ```sh
   ./build.sh
   uv run python -m unittest discover -s tests
   ```

Some analytical tests assert current dataset counts. Update an expectation
only when the count changed because of an intentional registry edit.

## Focused commands

Use these when you only need to regenerate or work on one part of the project:

- `uv run python -m scripts.validate_genealogy_data` validates registry references and evidence.
- `uv run python -m scripts.build_box_drawing_tree` regenerates `docs/trees/family_tree.md`.
- `uv run python -m scripts.build_genealogy_analytics` recreates the DuckDB database and JSON catalog.
- `uv run python -m scripts.render_genealogy_analytics_report` renders the analytics report.
- `uv run python -m scripts.sync_genealogy_analytics_dashboard` refreshes the dashboard data snapshot.
- `uv run python -m scripts.export_gedcom` writes the GEDCOM export.
- `uv run python -m scripts.build_cytoscape_genealogy_graph` and `uv run python -m scripts.build_family_chart` generate interactive trees.
- `uv run python -m scripts.build_dashboard` builds the analytics dashboard bundle.

## Generated artifacts and focused tests

The full build writes `docs/trees/family_tree.md`, analytics data and reports,
GEDCOM and interactive graph exports under ignored `artifacts/`, and the
dashboard snapshot and bundle. `docs/trees/family_tree.md` is generated and
should not be edited by hand. Run focused regression suites with
`uv run python -m unittest tests.test_genealogy_analytics` or
`uv run python -m unittest tests.test_family_chart`.

## Website updates

Edit a document, template, or photo mapping, then build and preview the website:

```sh
./build.sh site --serve
```

Open `http://127.0.0.1:4176/`. The build checks internal file links. The
preview does not publish the site. Use `./build.sh site` to build and check
without serving.

The page mapping, timeline selection, and photo folders are configured in
[`website/site.json`](website/site.json); templates and styles live in
`website/templates/`. See [the website workflow](website/README.md) for details.
When the preview is ready, ask Codex to **publish the latest site**.
