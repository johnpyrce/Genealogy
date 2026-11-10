# Importing GEDCOM into the registries

## GEDCOM source

A family tree is created in FamilySearch.org and then extracted as a GEDCOM file for
input into this genealogy.

- It is then extracted using RootsMagic Essentials.
- Extract the tree from FamilySearch using Sophie Pyrce and the root.  Her ID is "G4ZN-5FR".
- Extract the tree above and below her.
- Export the extracted tree from RootsMagic as a GEDCOM file at "data/source-material/PyrceFamily.ged".

## Current import (9 November 2026)

The 9 November export has been reconciled and applied: 74 GEDCOM people
(9 existing matches and 65 additions) and 26 families (2 reused and 24 additions).
The combined registries contain 236 people and 88 families. Repeating the same
import is idempotent. The current match file is fingerprinted to this export;
older exports can have different person numbers.

See the [research and complete GEDCOM definition](PyrceFamily-2026-11-09-research.md)
for the missing-date checklist, two recovered chart birth years, three unresolved
surnames, possible duplicate Jennifer profiles, and retained date conflict.
The commands below remain available for previewing or repeating the import.

## Refresh an existing source

Refresh treats a new extract as the current version of the existing GEDCOM
source. For the default input, S7 remains S7; no additional source is created.
Previewing never changes the registries or creates snapshot archives.

1. Ensure the previous export has a snapshot **before overwriting it**. Applied
   imports now create these automatically. For an older import, repeat its
   unchanged import with its reviewed matches and `--apply` to save the original:

   ```sh
   uv run python -m scripts.import_gedcom \
     --matches docs/imports/PyrceFamily.matches.json --apply
   ```

2. Export the updated tree from RootsMagic to `data/source-material/PyrceFamily.ged`.

3. Preview the refresh:

   ```sh
   uv run python -m scripts.import_gedcom --refresh \
     --report artifacts/imports/PyrceFamily.refresh.md
   ```

4. Review the report, then apply the same decisions:

   ```sh
   uv run python -m scripts.import_gedcom --refresh --apply \
     --report artifacts/imports/PyrceFamily.refreshed.md
   uv run python -m scripts.validate_genealogy_data
   ./build.sh
   uv run python -m unittest discover -s tests
   ```

The importer uses `_FSFTID` identifiers retained in evidence to keep person IDs
stable. It never carries changed GEDCOM record numbers forward as identities.
Duplicate FamilySearch IDs, contradictory decisions, or ambiguous matches block
applying. A person without a stable ID in a changed export needs a reviewed
`--matches` file: include their current GEDCOM reference and registry ID to match
them, or omit them to explicitly add a new person. Known stable-ID matches are
always reused, even when omitted from this refresh match file. For example:

```json
{"people": {"@I123@": 224}}
```

Supply that file with `--matches docs/imports/YourRefresh.matches.json` on both
preview and apply. If it has a `gedcom_sha256`, it must match the **new** export.
An older match file belongs to the older export and must not be reused blindly.

Refresh changes only the selected GEDCOM contribution:

- GEDCOM-owned names and exact years follow the new export, including clearing
  a previously supplied value when it becomes unknown. Qualified or ranged
  dates remain verbatim in evidence without an invented exact year.
- Populated chart-backed facts, Polish spellings, manually corrected fields,
  and custom family-name groups are retained. Supported incoming values can
  fill blank fields. Evidence records track fields managed by refresh so that
  subsequent extracts can update those fields without overwriting later edits.
- Source-only families are replaced. Families with evidence from another source
  remain, preserving alternative parentage. Unchanged family accounts keep their
  annotations and branch roles. A locally edited source-only family's membership
  blocks applying until reconciled rather than silently discarding the edit.
- Family IDs remain sequential. Evidence references are updated when families
  move; the report lists renumbering and removed families.
- People missing from the extract are not deleted: their registry IDs, facts,
  and historical identity evidence remain, marked absent for review. They remain
  in the combined registry and can reappear under the same ID on a later refresh.
- S7's description and other authored source metadata are retained; its file
  path, export date, current fingerprint, and imported evidence are refreshed.
  Website prose with snapshot-specific counts needs review after a data change.

To refresh S7 from a differently named input, provide that path and
`--source-id S7`; S7's current file path then points to that input. Refresh
requires a prior registered GEDCOM source; use append mode for its first import.

Snapshots live beside the selected input under
`gedcom-history/<source-id>/<sha256>/source.ged`. Refresh saves the preceding
registries in a content-addressed `registries-<hash>/` subdirectory there. Keep
these source-history files with the project; the live CSVs in `data/registries/`
remain authoritative. Archives are immutable and verified before replacement;
a failed CSV replacement restores the preceding CSVs. An interrupted apply may
leave a harmless complete archive. Both registry and incoming-file changes
since planning are rejected. Repeating an unchanged completed refresh is
idempotent.

If the old file was already overwritten before snapshots were enabled, recover
its original bytes and supply `--previous-gedcom path/to/original.ged`. The
fingerprint must match S7's registered previous version. Refresh will not
fabricate a complete original GEDCOM from partial evidence records.

## Matching

The direct importer **does not generate a match file automatically**. The
[command-line wrapper](command-line.md) can prepare proposed matches, which still
need review. Creating or updating the reviewed file means comparing GEDCOM names, dates, spouses,
parents, and children with the existing registries, then list only the people
who should match existing registry entries. Omit everyone who should be added.

The supplied match file includes a `gedcom_sha256` fingerprint for the reviewed
GEDCOM version. Re-exporting from RootsMagic can renumber people; if the file
changes, review and update the identity decisions and fingerprint before reusing
the match file. The importer rejects a fingerprint mismatch.

A match file has a `people` object mapping GEDCOM references to existing integer
person IDs:

```json
{"people": {"@I1@": 22}}
```

`"@I1@": 22` means GEDCOM person `@I1@` matches existing registry person **22**.
When a match file is supplied, people omitted from its `people` object are added
as **new people**, even if similar or identical names exist. An empty `people`
object adds everyone. Previously imported people are reused to avoid duplicates;
changing a previously imported match requires a separate registry reconciliation.

## Extraction

The GEDCOM and proposed match file are already in place. Start with these steps in Terminal.

1. **Update matches file:**

2. **Go to the repository:**

   ```sh
   cd /Users/johnpyrce/repos/Genealogy
   ```

3. **Preview the import:**

   ```sh
   uv run python -m scripts.import_gedcom \
     --matches docs/imports/PyrceFamily.matches.json \
     --report artifacts/imports/PyrceFamily.preview.md
   ```

   This displays proposed changes without modifying the registries.

4. **Review the [preview report](/Users/johnpyrce/repos/Genealogy/artifacts/imports/PyrceFamily.preview.md).**

   The current export is already imported, so a repeat preview should add no people or families. For a replacement export, review identities and conflicts before applying; the prior decisions cannot be reused solely by GEDCOM person number.

5. **Apply the import when satisfied:**

   ```sh
   uv run python -m scripts.import_gedcom \
     --matches docs/imports/PyrceFamily.matches.json \
     --apply \
     --report artifacts/imports/PyrceFamily.applied.json
   ```

   **This step writes the registry changes.**

6. **Validate and rebuild the derived outputs:**

   ```sh
   uv run python -m scripts.validate_genealogy_data
   ./build.sh
   ```

These append-mode commands use the current `data/source-material/PyrceFamily.ged`.
For a replacement extract, use refresh mode above. A changed export's match file
must be reviewed because GEDCOM person IDs can change.

## New input file

For a new input file, run a preview without `--matches` to identify straightforward
matches and uncertain candidates:

```sh
uv run python -m scripts.import_gedcom data/source-material/AnotherFamily.ged
```

An incomplete plan exits with status 2 and displays the decisions needed. Use
that output to prepare a match file manually, then repeat the preview with
`--matches` before applying it.

Without a match file, the importer matches only a unique compatible
normalized full name with at least one matching birth/death year. Normalization
ignores case and Polish diacritics for comparison; saved names retain their
original spelling. Similar names and uncertain identities are reported for
review and prevent writing the plan. English/Polish name equivalents are not
silently merged. Two GEDCOM people cannot map to the same registry person.

## Actions

The importer preserves all existing person rows and family rows. It appends
new people with stable IDs and new families in sequential row order. A family
already containing the incoming parents and children is reused. A different or
expanded account is retained as another family row rather than changing prior
relationships. New families default to `collateral`; select `--branch-role` if
another role is justified. A matching family keeps its existing branch role.

The importer adds a source entry, person-source evidence for every imported
person, and relationship evidence for the relationships actually supplied.
Evidence includes verbatim GEDCOM individual/family records, preserving dates,
places, qualifiers, notes, identifiers and relationship qualifiers. It does not
attribute unmentioned siblings to the imported source. Original GEDCOM records
remain the reference for other record types and pointer-based citations; this
is not a lossless GEDCOM-to-GEDCOM converter.

In append mode, existing names, dates, notes and source labels are never overwritten or filled
in. Qualified or ranged dates such as `ABT 1893` and `BET 1930 AND 1940` stay in
evidence without inventing an exact year. New evidence is `probable`; alternative
parentage evidence is `uncertain`. Importing family membership does not establish whether a
parent is biological, adoptive or a stepparent.

Reimporting the same file reuses source references and adds no duplicate rows.
A SHA-256 fingerprint prevents append mode from replacing an already registered
source; use refresh mode to replace its contribution, or preserve a changed GEDCOM
at a new source path to add an independent source. Every CSV is staged
before replacement, stale plans are rejected, and replacement errors restore
already replaced files. Derived trees, dashboard data, and exports are rebuilt
through the existing workflow after an actual import.
