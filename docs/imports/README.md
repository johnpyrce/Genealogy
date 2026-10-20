# Importing GEDCOM into the registries

## GEDCOM source

A family tree is created in FamilySearch.org and then extracted as a GEDCOM file for
input into this genealogy.

- It is then extracted using RootsMagic Essentials.
- Extract the tree from FamilySearch using Sophie Pyrce and the root.  Her ID is "G4ZN-5FR".
- Extract the tree above and below her.
- Export the extracted tree from RootsMagic as a GEDCOM file at "data/source-material/PyrceFamily.ged".

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

   It currently proposes **9 matches, 56 new people, and 21 new families**. Check the nine matches and the conflicting birth years. If something looks wrong, resolve it before continuing.

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

These commands use the current `data/source-material/PyrceFamily.ged`. If you replace it with another export, the match file must be reviewed and updated because GEDCOM person IDs can change.

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

Existing names, dates, notes and source labels are never overwritten or filled
in. Qualified or ranged dates such as `ABT 1893` and `BET 1930 AND 1940` stay in
evidence without inventing an exact year. New evidence is `probable`; alternative
parentage evidence is `uncertain`. Importing family membership does not establish whether a
parent is biological, adoptive or a stepparent.

Reimporting the same file reuses source references and adds no duplicate rows.
A SHA-256 fingerprint prevents replacing the contents of an already registered
source; preserve a changed GEDCOM at a new source path. Every CSV is staged
before replacement, stale plans are rejected, and replacement errors restore
already replaced files. Derived trees, dashboard data, and exports are rebuilt
through the existing workflow after an actual import.
