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
- `scripts.build_family_chart` writes the searchable family-chart tree under `artifacts/interactive/`.

Generate the family-chart viewer:

```sh
uv run python -m scripts.build_family_chart
```

Open `artifacts/interactive/family_tree.html` directly in a browser. All people
and relationships are embedded in the HTML; no server or separate data file is
required. The page loads pinned family-chart 0.9.0 and D3 7.9.0 assets from a
CDN, so viewing the chart requires internet access. Generation uses only Python's
standard library and requires no network access.

Search by name (with or without Polish accents) or exact person ID, then click a
result or press Enter to center its branch. IDs and dates distinguish people
with the same name. Click cards to explore related branches; the details panel
shows the selected person's dates, source, and notes.
The chart starts with two generations in each direction for readability;
the generation selector can expand this to four or all generations.
The source selector can limit the tree and search results to relationships
supported by one of the six chart documents. Its legend reports the number of
distinct people currently displayed, the number available in the selected
source, and the complete registry total.

Box colors can represent gender or normalized family name. Family colors are
assigned deterministically from `family_name_group`, remain stable across
filters and rebuilds, and appear in the legend only while that family is visible.
The **Show entire tree** button keeps the current source selection and renders
every connected group in that source as a scrollable forest. Detached couples
and standalone source labels remain visible as their own groups; clicking any
person returns to the focused branch view.

Use `--root 10` to choose the starting person and `--output path/to/tree.html`
to choose an output file. Gender styling follows explicit father/mother roles;
people without a recorded parent role use the neutral style. The viewer shows
the selected person's branch, with every registry person available in search.
When sources record alternative parent families, a selector preserves access to
each account and its note. The first listed family is displayed initially;
this display choice does not resolve conflicting evidence.

Run the generator regression tests with:

```sh
uv run python -m unittest tests.test_family_chart
```
