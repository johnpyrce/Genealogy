# FamilySearch command-line wrapper

The executable `genealogy` at the repository root automates the RootsMagic 12
workflow: create a separate database, download ancestors and descendants from
FamilySearch, export a new GEDCOM, and prepare an import preview. It runs locally
without requiring this chat. It uses the desktop app and requires an unlocked
macOS session.

## Setup

Requirements:

- macOS 14 or newer, with RootsMagic 12 installed in `/Applications/RootsMagic 12.app`.
- RootsMagic's interface in English and an accessible main window.
- Python 3.12+, `uv`, and Apple's Command Line Tools (`swiftc`).
- Accessibility and Screen Recording permission for the terminal running the command.

From the repository root:

```sh
./genealogy doctor
```

On first use, `doctor` compiles the repository-owned Swift helper into the ignored
`artifacts/tools/` directory. It does not install dependencies, change permissions,
or send UI input. If permissions are missing, enable them for your terminal in
**System Settings → Privacy & Security → Accessibility** and **Screen Recording**,
then restart that terminal and rerun `doctor`. macOS may call the latter setting
**Screen & System Audio Recording**.

The Python driver uses native accessibility controls for save dialogs and macOS
Vision OCR for RootsMagic's custom controls. It stops when an expected control is
missing or ambiguous. The driver was developed for RootsMagic 12's English UI;
major layout changes may require updates.

## Download and preview

```sh
./genealogy fetch --person G4ZN-5FR --ancestors 10 --descendants 4
```

These are also the defaults, so `./genealogy fetch` downloads from Sophie
Goscinski. The command creates a new local database before downloading. It does
not upload changes to FamilySearch. If FamilySearch opens a sign-in page, finish
the sign-in in your browser. The command waits up to ten minutes for sign-in,
and separately up to ten minutes for the download. Set `--timeout 1200` for a
longer wait. Do not interact with RootsMagic while the command is operating its
controls; browser sign-in is expected.

If a tree is already open, the wrapper uses RootsMagic's normal **Close File**
action before creating the new database. Complete a backup prompt in RootsMagic
if one appears; the command waits for it without changing your backup settings.

Each run uses a unique timestamp in America/Chicago and saves:

| Output | Location |
| --- | --- |
| Original GEDCOM export | `data/source-material/FamilySearch-<person>-<timestamp>.ged` |
| Separate RootsMagic database | `artifacts/imports/FamilySearch-<person>-<timestamp>/*.rmtree` |
| Proposed existing-person matches | Run folder's `matches.json` |
| Human-readable import preview | Run folder's `preview.md` |
| Full preview data | Run folder's `preview.json` |
| Parameters, export hash, counts, status | Run folder's `download.json` |
| Last UI observation and phase screenshots | Run folder's `ui/` |

Existing source files and databases are not overwritten. The wrapper checks the
exported people/family counts against RootsMagic's completion screen and checks
that the requested FamilySearch ID is present. A repository lock prevents two
fetches from controlling RootsMagic at the same time through this checkout.

### Proposed matches

When `data/source-material/PyrceFamily.ged` and
`docs/imports/PyrceFamily.matches.json` are available, the wrapper uses them to
carry previous **proposed** identity matches into the new export. It verifies the
previous file's fingerprint and links by the stable `_FSFTID` FamilySearch person
ID. It does not reuse GEDCOM record numbers, which can change between exports.

People omitted from that prior match file keep their proposed-addition status
when their FamilySearch IDs appear again. If a stable ID is already recorded in
registry import evidence, the existing registry person is reused instead. This
prevents duplicate additions after an earlier import. Conflicting IDs require
reconciliation before a preview can be prepared.

Specify a different prior pair with:

```sh
./genealogy fetch --person G4ZN-5FR \
  --previous-gedcom data/source-material/PreviousExport.ged \
  --previous-matches docs/imports/PreviousExport.matches.json
```

Use `--no-previous-matches` to discover candidates without carrying previous
proposals forward. New unambiguous name/year matches are included as proposals;
other possible overlaps remain unresolved. The generated match file lists only
proposed existing-person matches. Review it before importing: when subsequently
supplied as a reviewed `--matches` file, anyone omitted is treated as a new person.

## Review an existing export without downloading

Discover matches and save proposals and reports:

```sh
./genealogy preview data/source-material/YourExport.ged \
  --directory artifacts/imports/your-export-review
```

To carry proposed matches from an earlier export during discovery, pass both
`--previous-gedcom` and `--previous-matches`.

After reviewing/editing a generated `matches.json`, preview those exact decisions:

```sh
./genealogy preview data/source-material/YourExport.ged \
  --matches artifacts/imports/your-export-review/matches.json \
  --report artifacts/imports/your-export-review/reviewed.md
```

The fetch command prints the corresponding preview command for its actual files.

## Apply only after review

Fetching and previewing never apply registry changes. To apply reviewed matches,
use the existing importer with the actual GEDCOM and match paths printed by fetch:

```sh
uv run python -m scripts.import_gedcom data/source-material/YourExport.ged \
  --matches artifacts/imports/your-export-review/matches.json --apply
uv run python -m scripts.validate_genealogy_data
./build.sh
```

Run the affected regression tests after an intentional import. Some existing
tests assert dataset counts and need justified updates when the dataset grows.

## Failures and recovery

- Exit **0**: export and preview are ready, or the requested check passed.
- Exit **2**: the download/export succeeded, but the preview needs identity or family review.
- Exit **1**: an operation failed; inspect the printed message and run folder.
- Exit **130**: interrupted with Ctrl-C.

A failed fetch retains its database, any partial GEDCOM, `download.json`, and the
last UI screenshot/recognized labels. Do not import a partial GEDCOM. The command
does not close dialogs or delete these files on failure. Finish or cancel a
pending RootsMagic dialog manually before retrying; a new fetch starts a new run.
Use `./genealogy preview` to review a completed GEDCOM without downloading again.

Only the final export and proposed import are local files. FamilySearch sign-in
is handled by RootsMagic and your browser; the wrapper does not store passwords
or browser authorization URLs. Run artifacts contain family data and local UI
screenshots and remain ignored by Git. GEDCOM files remain untracked until you
explicitly choose to stage them.
