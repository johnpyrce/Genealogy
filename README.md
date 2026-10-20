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
| Work on website content, layout, or photos | `./build.sh site --serve` | Runs the full build, checks its internal links, then serves the website at `http://127.0.0.1:4176/` and opens it in your default browser. |

Omit `--serve` to build without starting a server: `./build.sh dashboard` or
`./build.sh site`. The site command **already runs the full build**, so there
is no need to run `./build.sh` immediately before it. Use `--port 4177` after
`site --serve` to choose another preview port.

`./preview_site.sh` remains available as a wrapper for `./build.sh site --serve`.
Use `./build.sh` for the full build and `./build.sh dashboard --serve` to rebuild
and preview the analytics dashboard. `./preview_site.sh --build-only` builds
the site without starting a server.

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

## Download from FamilySearch

The command-line wrapper downloads a tree through the RootsMagic desktop app,
exports a new GEDCOM, and prepares proposed matches and an import preview:

```sh
./genealogy doctor
./genealogy fetch --person G4ZN-5FR --ancestors 10 --descendants 4
```

Run from this repository on an unlocked Mac with RootsMagic 12 in English.
`doctor` builds the local helper using Apple's Command Line Tools and checks
Accessibility and Screen Recording permissions for the invoking terminal. If a
FamilySearch sign-in page opens, complete it in your browser; the command waits
and continues when sign-in finishes. Leave RootsMagic available while it runs.

Each run creates a new timestamped GEDCOM in `data/source-material/` and a run
folder under `artifacts/imports/` containing the separate RootsMagic database,
proposed `matches.json`, `preview.md`, `preview.json`, and `download.json`.
Source files and existing trees are preserved. Fetching does not change the
registries. Review the preview before using the import commands below.

The wrapper carries previous proposed matches forward by stable FamilySearch
IDs, using `PyrceFamily.ged` and its match file when available. Additional possible
overlaps are reported for review. See [the wrapper guide](docs/imports/command-line.md)
for setup, other input files, output details, and troubleshooting.

## GEDCOM import

The importer reads `data/source-material/PyrceFamily.ged` by default. Supply a
different repository path as a positional argument to import another GEDCOM.
Run the commands below from the repository root.

### How the match file is created

The direct importer **does not generate a match file automatically**. Create or
update it by comparing GEDCOM names, dates, spouses, parents, and children with
the existing registries. The command-line wrapper above can prepare proposed
matches for that review. The supplied
[`PyrceFamily.matches.json`](docs/imports/PyrceFamily.matches.json) was prepared
this way and contains proposed matches with explanations for review.

Its `people` section records each decision:

```json
{
  "people": {
    "@I1@": 22
  }
}
```

`"@I1@": 22` means GEDCOM person `@I1@` matches existing registry person **22**.
List only people who should match existing registry entries. When a match file
is supplied, everyone omitted from it is added as a **new person**, even if a
similar name exists. An empty `people` object adds everyone. Previously imported
people are reused so rerunning the same import does not create duplicates.

The supplied match file also contains a fingerprint tying the decisions to the
current GEDCOM export. Another export can renumber people, so review and update
the decisions and fingerprint whenever the input changes.

For a new GEDCOM, first run `uv run python -m scripts.import_gedcom <path>` without
`--matches`. The importer identifies straightforward matches and reports uncertain
candidates. It exits with an incomplete plan when decisions are needed. Use that
report to prepare the reviewed match file manually.

### Preview, review, and apply

1. Preview the supplied GEDCOM using the proposed match file. This does not
   change the registries:

   ```sh
   uv run python -m scripts.import_gedcom \
     --matches docs/imports/PyrceFamily.matches.json \
     --report artifacts/imports/PyrceFamily.preview.md
   ```

2. Open `artifacts/imports/PyrceFamily.preview.md`. Review the people matched,
   people added, families added, and conflicting facts. Correct any identity
   decisions in the match file and repeat the preview before applying.

3. Apply the reviewed import. **This step writes the registry changes:**

   ```sh
   uv run python -m scripts.import_gedcom \
     --matches docs/imports/PyrceFamily.matches.json \
     --apply \
     --report artifacts/imports/PyrceFamily.applied.json
   ```

4. Validate the registries and rebuild the derived outputs:

   ```sh
   uv run python -m scripts.validate_genealogy_data
   ./build.sh
   ```

Existing facts are preserved; incoming alternatives are retained in source
evidence. See [the detailed GEDCOM import guide](docs/imports/README.md) for the
source extraction process, matching rules, and provenance handling.

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
