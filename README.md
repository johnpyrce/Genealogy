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
- `uv run python -m scripts.build_pyrce_timeline` regenerates `docs/sections/joseph_sophie_timeline_vertical.svg` from `docs/sections/pyrce_events.csv`. The full build and website preview also run this step automatically.
- `uv run python -m scripts.build_genealogy_analytics` recreates the DuckDB database and JSON catalog.
- `uv run python -m scripts.render_genealogy_analytics_report` renders the analytics report.
- `uv run python -m scripts.sync_genealogy_analytics_dashboard` refreshes the dashboard data snapshot.
- `uv run python -m scripts.export_gedcom` writes the GEDCOM export.
- `uv run python -m scripts.build_cytoscape_genealogy_graph` and `uv run python -m scripts.build_family_chart` generate interactive trees.
- `uv run python -m scripts.build_dashboard` builds the analytics dashboard bundle.
- `./visit_report.sh` regenerates the visitor report and opens it in your browser;
  add `--export` to archive the latest online events first, or `--no-open` to
  generate without opening it.

## Download from FamilySearch

The command-line wrapper downloads a tree through the RootsMagic desktop app,
exports a new GEDCOM, and prepares proposed matches and an import preview:

```sh
./genealogy.sh doctor
./genealogy.sh fetch --person G4ZN-5FR --ancestors 10 --descendants 4
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

### Refresh the existing FamilySearch extract

Use `--refresh` when a new RootsMagic export should replace the previous
FamilySearch snapshot under the same source (S7), rather than add another source.
Save the new export over `data/source-material/PyrceFamily.ged`, then preview:

```sh
uv run python -m scripts.import_gedcom --refresh \
  --report artifacts/imports/PyrceFamily.refresh.md
```

Review the proposed fact updates, additions, superseded families, absent people,
and conflicts. When ready, apply and rebuild:

```sh
uv run python -m scripts.import_gedcom --refresh --apply \
  --report artifacts/imports/PyrceFamily.refreshed.md
uv run python -m scripts.validate_genealogy_data
./build.sh
uv run python -m unittest discover -s tests
```

Refresh matches by stable FamilySearch IDs, preserving registry person IDs even
when GEDCOM numbers change. It updates GEDCOM-managed facts and fills blank
chart-backed fields, while retaining populated chart-backed facts and local
corrections. Superseded GEDCOM-only families are replaced; people absent from the
new extract remain flagged for review. Missing or conflicting identities block
applying until reviewed with a new `--matches` file; do not reuse an older
export's match file.

Applied imports save immutable GEDCOM snapshots in
`data/source-material/gedcom-history/`. Refresh also archives the previous CSVs
before changing them. For a legacy import without a saved snapshot, apply an
unchanged append import **before overwriting the old export**, or supply the
original registered file with `--previous-gedcom`. The previous file's fingerprint
must match. See [the refresh guide](docs/imports/README.md#refresh-an-existing-source)
for details. The remaining import instructions describe append mode.

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

## Family profile

Run `./family_profile.sh` to build the profile from the project registries and
open `artifacts/interactive/family_profile.html` in your default browser. Family
profile characterizes the family tree along two dimensions: time, encoded by
generation with recorded birth years overlaid, and lineage, encoded
by the recorded main-line families. Four linked lenses show the shape of the
family (people per generation and gaps in the records),
a surname-by-generation heat map shaded by the number of people, per-segment
detail, and per-surname detail; clicking a segment, surname, or generation
highlights it across all lenses.

The **Relationship Graph** tab uses the same source and offers both People and
Families views. The graph loads Cytoscape.js from a CDN when you open the tab.

To build and open a profile directly from a UTF-8 GEDCOM export, run:

```sh
./family_profile.sh --gedcom path/to/tree.ged
```

To combine several exports in one profile, pass all the files together:

```sh
./family_profile.sh --gedcom path/to/first.ged path/to/second.ged
```

The combined view opens `artifacts/interactive/merged_family_profile.html`.
Shared, unambiguous FamilySearch IDs or GEDCOM UIDs link people across files.
File-local record IDs and names alone do not link people. Identical family
memberships appear once with their source references. Different family accounts
stay separate, and disagreements in recorded years are shown in the profile
and person details.

The script opens `artifacts/interactive/tree_family_profile.html`. Pass
`--output` to choose another destination. The builder reads people and
relationships directly from the GEDCOM and leaves the registries untouched.
The GEDCOM profile displays recorded parents, partners, and children alongside
generation and surname views. Branch roles are unavailable in this mode.

To generate the HTML without opening a browser, run
`uv run python -m scripts.build_family_profile` with the same input and output options.

## Backups

- The GED files and registeries with only the Muszyna data and the GED file with
only the Pyrce family data from FamilySearch.org are backed up to
artifacts/backups/before-familysearch-merge.  Use these to recover just these states.
