"""Replace one GEDCOM snapshot without discarding independently authored facts."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile

from scripts.lib.genealogy_data import ROOT, REGISTRIES, load_registry_csv


MANAGED = "Refresh managed fields: "
ABSENT = " Refresh status: absent; retained for identity/review only."
FACTS = ("first_name", "surname", "family_name_group", "birth_year", "death_year")


def snapshot_path(path: Path, source_id: str, checksum: str, registry_dir: Path = REGISTRIES) -> Path:
    """Store immutable source versions beside the original input, outside artifacts."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", source_id):
        raise ValueError("Source ID cannot be used as a snapshot directory")
    parent = path.parent if registry_dir.resolve() == REGISTRIES.resolve() else registry_dir.parent
    return parent / "gedcom-history" / source_id / checksum / "source.ged"


def csv_bytes(headers: list[str], rows: list[dict]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def family_key(row: dict) -> tuple:
    return row["father_id"], row["mother_id"], frozenset(filter(None, row["children_ids"].split(";")))


def managed_fields(note: str) -> dict:
    if MANAGED not in note:
        return {}
    try:
        fields = json.loads(note.split(MANAGED, 1)[1].splitlines()[0].replace(ABSENT, ""))
    except (ValueError, IndexError) as error:
        raise ValueError("Invalid refresh ownership metadata in person evidence") from error
    if not isinstance(fields, dict) or any(k not in FACTS or not isinstance(v, str) for k, v in fields.items()):
        raise ValueError("Invalid refresh ownership metadata in person evidence")
    return fields


def make_refresh_plan(path: Path, registry_dir: Path = REGISTRIES,
                      decisions: dict[str, int] | None = None,
                      source_id: str | None = None, branch_role: str = "collateral", *,
                      previous_gedcom: Path | None = None) -> dict:
    """Preview a three-way reconciliation of incoming, previous, and registry facts.

    Source-only relationships are replaced, shared families remain, and missing
    people keep their IDs plus historical identity evidence. Nothing is written
    until apply_plan, including source and registry archives.
    """
    from scripts.import_gedcom import (
        REGISTRY_PATHS, incoming_person, label, make_plan, parse_records, validate_records,
    )

    path = path.resolve()
    relative = path.relative_to(ROOT).as_posix()
    incoming_bytes = path.read_bytes()
    checksum = hashlib.sha256(incoming_bytes).hexdigest()
    records = parse_records(incoming_bytes.decode("utf-8-sig"))
    validate_records(records)
    individuals = [r for r in records if r.tag == "INDI"]
    headers, tables, originals = {}, {}, {}
    for registry_path in REGISTRY_PATHS:
        name = registry_path.name
        headers[name], tables[name] = load_registry_csv(registry_dir / name)
        originals[name] = (registry_dir / name).read_bytes()
    sources = tables["sources.csv"]
    candidates = [r for r in sources if r["source_id"] == source_id] if source_id else [
        r for r in sources if r["file_name"] == relative]
    if len(candidates) != 1 or candidates[0]["source_type"].upper() != "GEDCOM":
        raise ValueError("Refresh requires one existing GEDCOM source; select it with --source-id or import the file first")
    source = candidates[0]
    if any(r is not source and r["file_name"] == relative for r in sources):
        raise ValueError("Incoming GEDCOM path is already registered under a different source")
    source_id = source["source_id"]
    source_path = ROOT / source["file_name"]
    hashes = re.findall(r"sha256:([a-f0-9]{64})", source["repository_note"])
    if len(hashes) != 1:
        raise ValueError("Refresh requires exactly one current source SHA-256 fingerprint")
    old_hash = hashes[0]
    previous = previous_gedcom.resolve() if previous_gedcom else snapshot_path(source_path, source_id, old_hash, registry_dir)
    if not previous_gedcom and not previous.is_file():
        previous = source_path
    previous_bytes = previous.read_bytes() if previous.is_file() else b""
    if hashlib.sha256(previous_bytes).hexdigest() != old_hash:
        raise ValueError("Previous GEDCOM snapshot unavailable or fingerprint mismatch. Supply --previous-gedcom with the original registered export. Before overwriting a legacy input, run an unchanged import with --apply to save its snapshot.")
    old_records = parse_records(previous_bytes.decode("utf-8-sig"))
    validate_records(old_records)
    person_rows = tables["people.csv"]
    by_id = {int(r["id"]): r for r in person_rows}
    if len(by_id) != len(person_rows):
        raise ValueError("Existing person IDs are duplicated")
    families = tables["families.csv"]
    if [r["id"] for r in families] != [str(i) for i in range(1, len(families) + 1)]:
        raise ValueError("Existing family IDs are not sequential")
    person_evidence = tables["person_source_evidence.csv"]
    evidence = tables["relationship_evidence.csv"]
    prior_rows = [r for r in person_evidence if r["source_id"] == source_id]
    old_by_person, old_xrefs, stable_ids = {}, {}, {}
    for row in person_evidence:
        if not row["location"].startswith("GEDCOM "):
            continue
        parsed = parse_records(row["transcription"])
        if len(parsed) != 1 or parsed[0].tag != "INDI":
            raise ValueError("Invalid GEDCOM individual evidence; reconcile before refreshing")
        record = parsed[0]
        identifier = record.get("_FSFTID")
        person_id = int(row["person_id"])
        if person_id not in by_id:
            raise ValueError("GEDCOM evidence refers to an unknown registry person")
        if identifier:
            if identifier in stable_ids and stable_ids[identifier] != person_id:
                raise ValueError(f"FamilySearch ID {identifier} maps to multiple registry people")
            stable_ids[identifier] = person_id
        if row["source_id"] == source_id:
            if person_id in old_by_person:
                raise ValueError("Multiple previous records map to one person in the refreshed source")
            old_by_person[person_id] = (record, row)
            if row["location"].startswith("GEDCOM @"):
                old_xrefs[record.xref] = str(person_id)
    if len(old_by_person) != len(prior_rows):
        raise ValueError("Refresh requires imported individual evidence for every prior source person")
    old_people = [r for r in old_records if r.tag == "INDI"]
    if set(old_xrefs) != {r.xref for r in old_people}:
        raise ValueError("Previous GEDCOM people do not match current source evidence")
    for record in old_people:
        stored = old_by_person[int(old_xrefs[record.xref])][0]
        if stored.raw() != record.raw():
            raise ValueError("Previous GEDCOM differs from its retained individual evidence")

    # Neither reordered GEDCOM numbers nor a sparse match file can override a
    # known stable identity. Explicit decisions resolve records without IDs.
    resolved = dict(decisions or {})
    incoming_stable = set()
    for record in individuals:
        identifier = record.get("_FSFTID")
        if identifier:
            if identifier in incoming_stable:
                raise ValueError(f"Duplicate FamilySearch ID {identifier} in incoming GEDCOM")
            incoming_stable.add(identifier)
        target = stable_ids.get(identifier)
        if target is None and checksum == old_hash:
            target = int(old_xrefs[record.xref])
        if target is not None:
            if record.xref in resolved and resolved[record.xref] != target:
                raise ValueError(f"{record.xref}: explicit decision contradicts FamilySearch identity")
            resolved[record.xref] = target
    if len(resolved.values()) != len(set(resolved.values())):
        raise ValueError("Multiple incoming people map to one registry person")

    expected = {}
    for record in old_records:
        if record.tag == "FAM":
            expected[record.xref] = (
                old_xrefs.get(record.get("HUSB"), ""), old_xrefs.get(record.get("WIFE"), ""),
                frozenset(old_xrefs[r.value] for r in record.all("CHIL")),
            )
    external_families = {r["family_id"] for r in evidence if r["source_id"] != source_id}
    removable, blocked = [], []
    for row in families:
        attached = [r for r in evidence if r["family_id"] == row["id"] and r["source_id"] == source_id]
        if not attached or row["id"] in external_families:
            continue
        accounts = {r["location"].removeprefix("GEDCOM ") for r in attached}
        if not row["note"].startswith(source_id + " ") or not any(
                expected.get(xref) == family_key(row) for xref in accounts):
            blocked.append(dict(name="locally edited family", id=row["id"],
                                reason="Source-only family differs from the previous GEDCOM; reconcile its edits before refresh"))
        else:
            removable.append(row)
    removed_ids = {r["id"] for r in removable}
    retained = [r for r in families if r["id"] not in removed_ids]
    renumber = {r["id"]: str(i) for i, r in enumerate(retained, 1)}
    for row in retained:
        row["id"] = renumber[row["id"]]
    tables["families.csv"] = retained
    tables["relationship_evidence.csv"] = [
        dict(r, family_id=renumber[r["family_id"]]) for r in evidence if r["source_id"] != source_id]
    tables["person_source_evidence.csv"] = [r for r in person_evidence if r["source_id"] != source_id]
    source["file_name"] = relative
    source["source_date"] = records[0].get("DATE")
    source["repository_note"] = source["repository_note"].replace("sha256:" + old_hash, "sha256:" + checksum)

    # Reuse the conservative importer to build current evidence and reconcile
    # shared families; all staging is disposable until the completed plan applies.
    with tempfile.TemporaryDirectory(prefix=".gedcom-refresh-", dir=registry_dir) as temporary:
        staging = Path(temporary)
        for name, rows in tables.items():
            (staging / name).write_bytes(csv_bytes(headers[name], rows))
        if decisions is None:
            planned = make_plan(path, staging, source_id=source_id, branch_role=branch_role,
                                match_overrides=resolved)
        else:
            planned = make_plan(path, staging, decisions=resolved, source_id=source_id, branch_role=branch_role)
        final = {}
        for name in tables:
            content = planned["changed"].get(name, (staging / name).read_bytes())
            final[name] = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    report = planned["report"]
    report.update(operation="refresh", previous_sha256=old_hash, people_updated=[],
                  people_absent=[], families_removed=[], family_ids_changed=[])
    report["unresolved"].extend(blocked)
    if decisions is None:
        report["unresolved"].extend(dict(gedcom_id=r.xref, name=r.get("NAME"),
            reason="No FamilySearch ID; provide a reviewed --matches file to match this person or explicitly add them")
            for r in individuals if not r.get("_FSFTID") and r.xref not in resolved)
    report["conflicts"] = [c for c in report["conflicts"] if "parentage also recorded" in c]
    final_people = {int(r["id"]): r for r in final["people.csv"]}
    final_evidence = {r["location"]: r for r in final["person_source_evidence.csv"] if r["source_id"] == source_id}
    current_ids = {int(r["id"]) for key in ("people_added", "people_matched") for r in report[key]}
    matches = {r["gedcom_id"]: r for r in report["people_matched"]}
    externally_backed = {int(r["person_id"]) for r in person_evidence if r["source_id"] != source_id}
    externally_backed.update(int(r[k]) for r in evidence if r["source_id"] != source_id
                             for k in ("person_id", "related_person_id") if r[k])
    refresh_note = "Refresh preserves chart-backed and locally edited facts; managed fields follow the current extract."
    for added in report["people_added"]:
        row = final_people[int(added["id"])]
        evidence_row = final_evidence["GEDCOM " + added["gedcom_id"]]
        evidence_row["note"] = evidence_row["note"].replace("Existing registry facts retained.", refresh_note)
        evidence_row["note"] += "\n" + MANAGED + json.dumps(
            {field: row[field] for field in FACTS}, ensure_ascii=False, sort_keys=True)
    for record in individuals:
        if record.xref not in matches:
            continue
        match = matches[record.xref]
        person_id = int(match["id"])
        row = final_people[person_id]
        incoming = incoming_person(record)
        prior = old_by_person.get(person_id)
        previous_values = incoming_person(prior[0]) if prior else {}
        managed = managed_fields(prior[1]["note"]) if prior else {}
        owned_person = bool(prior and row["source"] == "gedcom" and person_id not in externally_backed)
        if (prior and prior[0].get("_FSFTID") and record.get("_FSFTID")
                and prior[0].get("_FSFTID") != record.get("_FSFTID") and record.xref not in resolved):
            report["unresolved"].append(dict(gedcom_id=record.xref, name=label(row),
                reason="Name match has a different previous FamilySearch ID; review an explicit identity decision"))
        original_surname = row["surname"]
        changes, ownership = {}, {}
        for field in FACTS:
            old, new = row[field], incoming[field]
            if field in managed:
                can_update = old == managed[field]
            elif owned_person:
                can_update = old == previous_values[field]
            else:
                can_update = not old or (field == "family_name_group" and old == "Unknown" and not original_surname)
            if field == "family_name_group" and row["surname"] != incoming["surname"]:
                can_update = False
            if can_update:
                row[field] = new
                ownership[field] = new
                if old != new:
                    changes[field] = dict(before=old, after=new)
            elif old != new and (new or field in managed or owned_person):
                report["conflicts"].append(f"{record.xref} → person {person_id}: {field} registry {old!r}; GEDCOM {new!r}. Chart-backed or locally edited value retained.")
        row["note"] = row["note"].replace(ABSENT, "")
        evidence_row = final_evidence["GEDCOM " + record.xref]
        if prior:
            evidence_row["note"] = prior[1]["note"].split("\n" + MANAGED, 1)[0].replace(ABSENT, "")
        evidence_row["note"] = evidence_row["note"].replace("Existing registry facts retained.",
            refresh_note)
        if ownership:
            evidence_row["note"] += "\n" + MANAGED + json.dumps(ownership, ensure_ascii=False, sort_keys=True)
        if changes:
            report["people_updated"].append(dict(gedcom_id=record.xref, id=person_id, name=label(row), fields=changes))
    for person_id, (record, old_evidence) in old_by_person.items():
        if person_id in current_ids:
            continue
        report["people_absent"].append(dict(id=person_id, name=label(by_id[person_id]), familysearch_id=record.get("_FSFTID")))
        row = final_people[person_id]
        if ABSENT not in row["note"]:
            row["note"] += ABSENT
        preserved = dict(old_evidence, location=f"GEDCOM absent person {person_id}")
        preserved["note"] = preserved["note"].replace(ABSENT, "") + ABSENT
        final["person_source_evidence.csv"].append(preserved)
    # Preserve deliberate branch roles on replaced families, following identity
    # membership rather than a potentially renumbered GEDCOM family reference.
    old_roles = {family_key(r): r["branch_role"] for r in removable}
    old_family_rows = {family_key(r): r for r in removable}
    pair_roles = {}
    for row in removable:
        pair_roles.setdefault(family_key(row)[:2], set()).add(row["branch_role"])
    final_keys = {}
    for row in final["families.csv"]:
        key = family_key(row)
        final_keys.setdefault(key, []).append(row["id"])
        if row["note"].startswith(source_id + " "):
            roles = pair_roles.get(key[:2], set())
            row["branch_role"] = old_roles.get(key, next(iter(roles)) if len(roles) == 1 else row["branch_role"])
            if key in old_family_rows:
                # Keep annotations on an unchanged account while correcting its
                # source reference when the new export renumbers family records.
                old_note = old_family_rows[key]["note"]
                new_prefix = row["note"].split(":", 1)[0]
                row["note"] = re.sub(r"^" + re.escape(source_id) + r" @[^@]+@", lambda _: new_prefix,
                                     old_note, count=1)
    for old in removable:
        equivalent = final_keys.get(family_key(old), [])
        if len(equivalent) == 1:
            renumber[old["id"]] = equivalent[0]
        else:
            report["families_removed"].append(dict(old, gedcom_id="previous snapshot"))
    for row in final["families.csv"]:
        def update_references(match: re.Match) -> str:
            ids = re.findall(r"\d+", match.group(1))
            if all(old_id in renumber for old_id in ids):
                return "Alternative parentage also recorded in families " + ", ".join(renumber[i] for i in ids) + ";"
            return "Alternative parentage also recorded in archived snapshot families " + ", ".join(ids) + ";"

        row["note"] = re.sub(r"Alternative parentage also recorded in families ([\d, ]+);",
                             update_references, row["note"])
    genuinely_added = []
    for row in report["families_added"]:
        if family_key(row) in old_roles:
            report["families_matched"].append(row)
        else:
            genuinely_added.append(row)
    report["families_added"] = genuinely_added
    report["family_ids_changed"] = [dict(before=k, after=v) for k, v in renumber.items() if k != v]
    report["ready"] = not report["unresolved"]
    changed = {name: csv_bytes(headers[name], rows) for name, rows in final.items()
               if csv_bytes(headers[name], rows).decode() != originals[name].decode().replace("\r\n", "\n")}
    report["changed_files"] = list(changed)
    prior_archive = snapshot_path(source_path, source_id, old_hash, registry_dir)
    archives = {prior_archive: previous_bytes, snapshot_path(path, source_id, checksum, registry_dir): incoming_bytes}
    if changed:
        registry_hash = hashlib.sha256(b"".join(originals[n] for n in sorted(originals))).hexdigest()
        archives.update({prior_archive.parent / ("registries-" + registry_hash) / name: content
                         for name, content in originals.items()})
    report["archives"] = [p.relative_to(ROOT).as_posix() for p in archives]
    return dict(report=report, changed=changed, originals=originals, registry_dir=registry_dir,
                input_checks={path: incoming_bytes}, archives=archives)
