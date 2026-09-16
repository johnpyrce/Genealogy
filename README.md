# Combined Muszyna family tree — English edition

The merged tree combines and translates six supplied genealogy charts for the
Gościński, Miczulski, Pyrc, and Rams families. Polish personal and place names
are preserved; relationship labels and explanatory text are in English. The SVG
is the editable master and the PNG is the convenient viewing copy.

## Source reconciliation notes

- Jan Gościński (1888–1970) and Marianna née Miczulska (1895–1962) are the
  bridge between the historical Gościński chart and the handwritten chart.
- Bronisława née Gościńska (1930–2015) and Bolesław Rams (1924–2002) bridge the
  Gościński and Rams charts.
- The polished modern chart expands Wanda Gościńska's branch. The later
  handwritten charts also name Antonina, Elżbieta, Małgorzata, and possibly Bogdan and
  Pluto as children of Stanisław Gościński and Władysława Miczulska. Those
  additional readings are explicitly marked uncertain in the merged tree.
- “zd.” means *z domu* (née). A plus sign in the printed sources is interpreted
  as a death-date marker rather than arithmetic.
- The later handwritten Gościński–Pyrc chart adds Zofia Gościńska as a child
  of Franciszek and Józefa, and adds Emil and Stanisław among the Pyrc children.
  The printed chart has a different sibling list, so both readings are retained
  as a documented conflict.
- The printed Gościński chart also shows Jakub Gościński (1788) and Stanisław
  Gościński (1785) near Wawrzyniec Gościński (1780), but the exact connecting
  lines are not clear enough to assert their parentage.
- Later handwritten additions include Teresa, Marta, and Barbara under
  Bronisław and Władysława Śliwa; Marek under Edward and Anna Maślanka; and
  Mariusz under Jan and Zofia Jacenik.
- Illegible handwritten names were not silently invented. The merged chart is
  a working synthesis and should be checked against parish or civil records.

## Files

- `merged_muszyna_family_tree.svg` — editable vector master
- `merged_muszyna_family_tree.png` — rendered image
- `english_chart_transcription.md` — chart-by-chart English transcription and
  explanation of unresolved readings
- `merged_family_tree_outline.md` — consolidated indented Markdown family tree
  with source conflicts and uncertain relationships marked inline
- `merged_family_tree_box_drawing.md` — monospaced Unicode tree using box
  drawing connectors, generated from the consolidated outline
- `merged_family_tree_box_drawing.png` and `.svg` — rendered versions of the
  text tree in a fixed-width JetBrains Mono font with zero letter spacing
- `genealogy_statistics.md` — statistical summary of people, tree depth and
  width, dates, surnames, first names, and earliest recorded people
- `genealogy_people_registry.csv` — auditable person-level registry used for
  the calculations
- `genealogy_family_registry.csv` — editable relationship registry; each row
  records a father ID, mother ID, semicolon-separated child IDs, branch role,
  and source note. Branch roles are `main_line`, `spouse_ancestry`, or `collateral`
- `genealogy_data.py` — shared loader for the relationship registry
- `build_genealogy_analytics.py` — rebuilds an ignored DuckDB analytical layer and a reviewable JSON metric catalog from the CSV registries; it normalizes packed child lists into family-child and parent-child tables before calculating the seven approved reporting domains
- `genealogy_analytics.json` — generated, reviewable output for inventory, completeness, evidence, tree structure, family structure, temporal, and names/identity reporting
- `genealogy_sources.csv` — catalog of the six original chart images, with
  stable source IDs (`S1`–`S6`)
- `genealogy_relationship_evidence.csv` — source citation, chart location,
  transcription, confidence, and notes for every family relationship record
- `validate_genealogy_data.py` — checks IDs, evidence coverage, confidence
  values, and the existence of every cited source chart
- `merged_muszyna_family_tree.ged` — GEDCOM 5.5.1 exchange file for import
  into genealogy programs; includes all 156 registry entries and the
  reconciled relationships, with notes retained for uncertain links
- `family_graph_primary.svg` and `.png` — concise relationship graph containing
  the primary family lines; `family_graph.svg` and `.png` are matching aliases
- `family_graph_complete.svg` and `.png` — complete graph including spouse
  ancestry and collateral families
- `build_family_graph.py` — reproducibly regenerates the family-level graph
- `tadeusz_pyrc_direct_ancestors.csv` — direct ancestors of Tadeusz Pyrc, with
  generation, relationship path, and source-chart provenance for each link
- `tadeusz_pyrc_ancestor_tree.svg` and `.png` — direct-ancestor tree with the
  oldest documented people at the top and chart IDs on parental links
- `tadeusz_pyrc_ancestor_report.md` — generation summary, terminal ancestral
  lines, evidence references, and interpretation limits
- `build_direct_ancestor_tree.py` — reproducibly regenerates those four
  Tadeusz Pyrc ancestor outputs
- `genealogy_relationship_graph.html` — the interactive Cytoscape.js
  relationship graph; the page embeds the current registry data and loads
  Cytoscape from its CDN
- `build_cytoscape_genealogy_graph.py` — reproducibly generates the interactive
  graph from the people, family, source, and relationship-evidence registries
- `export_gedcom.py` — reproducibly regenerates the GEDCOM export from the
  person registry and documented relationship map

## Analytics

The CSV registries remain the editable source of truth. DuckDB is an analytical
cache only: it is recreated from the CSV files whenever analytics are built and
is ignored by Git. To rebuild the normalized tables and report-ready results:

```sh
uv run python build_genealogy_analytics.py
```

This creates `genealogy_analytics.duckdb` (local cache) and
`genealogy_analytics.json` (reviewable result). Use `--database` or `--output`
to direct either artifact elsewhere.

To run the analytical regression checks:

```sh
uv run python -m unittest test_genealogy_analytics.py
```

Render a standalone Markdown report from an already-built database (without
reading the CSV files again):

```sh
uv run python render_genealogy_analytics_report.py
```

This writes `genealogy_analytics_report.md`. Pass `--database`, `--output`, or
`--title` to render a different DuckDB file, destination, or report heading.

## HTML analytics dashboard

The interactive report is a compiled snapshot of the DuckDB analytical output.
Refresh its reviewed data after rebuilding the database, then rebuild the HTML
app from the repository root:

```sh
uv run python build_genealogy_analytics.py
uv run python sync_genealogy_analytics_dashboard.py
node /Users/johnpyrce/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.8/scripts/data-app.mjs build \
  --project-dir "$PWD/genealogy-statistics-report" --separate-data
```

Serve the built app over HTTP rather than opening its `index.html` directly:

```sh
python3 -m http.server 4175 --bind 127.0.0.1 \
  --directory genealogy-statistics-report/dist
```

Open `http://127.0.0.1:4175/?view=1`. The sync command keeps the app's stable
identity while replacing only its reviewed analytical rows and provenance.
