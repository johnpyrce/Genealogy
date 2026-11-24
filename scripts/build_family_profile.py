"""Build a standalone family profile app characterizing the family tree.

Two dimensions: time, encoded primarily by generation (to cope with the many
missing dates) and secondarily by recorded birth years; and lineage, encoded
by main-line segments, branches, and spouse ancestry. This generator is fully
separate from the website build chain. It reads the registries by default or
uses supplied GEDCOM files to write a self-contained HTML artifact.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import webbrowser

from scripts.build_cytoscape_genealogy_graph import (
    add_family_generations,
    dataset as registry_graph_data,
    render_html as render_graph_html,
)
from scripts.build_generation_overview import generation_layout
from scripts.import_gedcom import incoming_person, parse_gedcom
from scripts.lib.genealogy_data import FAMILY_REGISTRY, ROOT, load_people, load_registry_csv

TEMPLATE = ROOT / "scripts/templates/family_profile.html"
LAYERS_SCRIPT = TEMPLATE.with_name("generation_layers.js")


def load_families_with_roles() -> list[tuple[int | None, int | None, list[int], str]]:
    """Return (father, mother, children, branch_role) tuples from the family CSV.

    The shared load_families normalizes note into the fourth slot; the profile
    additionally needs branch_role, so read the registry through the shared
    low-level loader instead.
    """
    _, rows = load_registry_csv(FAMILY_REGISTRY)
    families = []
    for row in rows:
        father = int(row["father_id"]) if row["father_id"] else None
        mother = int(row["mother_id"]) if row["mother_id"] else None
        children = [int(value) for value in row["children_ids"].split(";") if value]
        families.append((father, mother, children, row["branch_role"]))
    return families


def compute_segments(
    people: list[dict], families: list[tuple], placements: dict
) -> tuple[dict[int, int], list[dict], list[dict]]:
    """Assign main-line persons to named lineage segments.

    A main-line family needs a recorded father to extend a lineage. Segments
    start at every main-line father who is not recorded as a child of a
    main-line family; each segment then absorbs, through main-line links only,
    the partners of its main-line families and their children. Persons that
    head main-line families yet are unreachable from any start (cycles of
    contradictory parentage) are not assigned to a segment; they are reported
    as main-line inconsistencies with the family links involved.
    """
    main_fams: dict[int, tuple[int, int | None, list[int]]] = {}
    fams_by_father: dict[int, list[int]] = defaultdict(list)
    child_of_main: set[int] = set()
    for fid, (father, mother, children, role) in enumerate(families, 1):
        if role == "main_line" and father is not None:
            main_fams[fid] = (father, mother, children)
            fams_by_father[father].append(fid)
            child_of_main.update(children)

    starts = sorted(
        set(fams_by_father) - child_of_main,
        key=lambda pid: (placements[pid]["generation"] or 10**6, pid),
    )
    assignment: dict[int, int] = {}
    member_sets: list[set[int]] = []
    for start in starts:
        index = len(member_sets)
        member_sets.append({start})
        assignment[start] = index
        stack = [start]
        while stack:
            current = stack.pop()
            for fid in fams_by_father.get(current, []):
                _, mother, children = main_fams[fid]
                for pid in ([mother] if mother is not None else []) + list(children):
                    if pid not in assignment:
                        assignment[pid] = index
                        member_sets[index].add(pid)
                        stack.append(pid)

    child_fams: dict[int, list[int]] = defaultdict(list)
    for fid, (_, _, children) in main_fams.items():
        for child in children:
            child_fams[child].append(fid)
    inconsistencies = [
        {
            "person": pid,
            "child_of": child_fams.get(pid, []),
            "heads": fams_by_father.get(pid, []),
        }
        for pid in sorted(set(fams_by_father) - set(assignment))
    ]

    by_id = {person["id"]: person for person in people}
    segments = []
    for index, start in enumerate(starts):
        gens = [placements[p]["generation"] for p in member_sets[index]]
        aligned = [g for g in gens if g > 0]
        start_person = by_id[start]
        segments.append(
            {
                "index": index,
                "label": f"{start_person['first']} {start_person['surname']}".strip(),
                "group": start_person["surname_group"],
                "start": start,
                "start_generation": placements[start]["generation"],
                "min_generation": min(aligned) if aligned else 0,
                "max_generation": max(aligned) if aligned else 0,
                "members": len(member_sets[index]),
            }
        )
    return assignment, segments, inconsistencies


def load_gedcom_profile(path: Path) -> tuple[list[dict], list[tuple], list[str]]:
    """Load people and family links directly from a validated GEDCOM export."""
    records = parse_gedcom(path)
    people = []
    ids = {}
    for record in records:
        if record.tag != "INDI":
            continue
        facts = incoming_person(record)
        person_id = len(people) + 1
        ids[record.xref] = person_id
        people.append({
            "id": person_id,
            "first": facts["first_name"],
            "surname": facts["surname"],
            "surname_group": facts["family_name_group"],
            "birth": int(facts["birth_year"]) if facts["birth_year"] else None,
            "death": int(facts["death_year"]) if facts["death_year"] else None,
            "reference": record.xref,
            "identity": {
                (namespace, value.strip().upper())
                for namespace, tag in (("familysearch", "_FSFTID"), ("uid", "_UID"), ("uid", "UID"))
                for entry in record.all(tag)
                if (value := entry.value).strip()
            },
        })

    families = []
    references = []
    for record in records:
        if record.tag == "FAM":
            families.append((
                ids.get(record.get("HUSB")),
                ids.get(record.get("WIFE")),
                [ids[child.value] for child in record.all("CHIL")],
                None,
            ))
            references.append(record.xref)
    return people, families, references


def merge_gedcom_profiles(paths: list[Path]) -> tuple[list[dict], list[tuple], list[str]]:
    """Combine file-local records, linking people only through unambiguous persistent IDs."""
    labels = Counter(path.name for path in paths)
    loaded = []
    records = {}
    by_identity = defaultdict(list)
    for index, path in enumerate(paths):
        label = path.name if labels[path.name] == 1 else f"{path.name} (file {index + 1})"
        try:
            people, families, references = load_gedcom_profile(path)
        except (OSError, ValueError) as error:
            raise ValueError(f"{path}: {error}") from error
        loaded.append((label, families, references))
        for person in people:
            key = (index, person["id"])
            records[key] = person
            for identity in person["identity"]:
                by_identity[identity].append(key)

    merged_people = []
    merged_ids = {}
    visited = set()
    for key in records:
        if key in visited:
            continue
        pending = [key]
        visited.add(key)
        identities = set()
        for person_key in pending:
            for identity in records[person_key]["identity"] - identities:
                identities.add(identity)
                for match in by_identity[identity]:
                    if match not in visited:
                        pending.append(match)
                        visited.add(match)
        unique_within_files = len({index for index, _ in pending}) == len(pending)
        familysearch_ids = {value for namespace, value in identities if namespace == "familysearch"}
        groups = [sorted(pending)] if unique_within_files and len(familysearch_ids) <= 1 else [
            [member] for member in sorted(pending)
        ]
        for group in groups:
            person_id = len(merged_people) + 1
            for member in group:
                merged_ids[member] = person_id
            person = merge_gedcom_person([records[member] for member in group], person_id)
            person["reference"] = "; ".join(
                f"{loaded[index][0]} {records[index, local_id]['reference']}"
                for index, local_id in group
            )
            merged_people.append(person)

    merged_families = []
    family_sources = []
    matching_families = {}
    for index, (label, families, references) in enumerate(loaded):
        for (father, mother, children, role), reference in zip(families, references, strict=True):
            father = merged_ids[index, father] if father is not None else None
            mother = merged_ids[index, mother] if mother is not None else None
            children = list(dict.fromkeys(merged_ids[index, child] for child in children))
            signature = (father, mother, frozenset(children))
            # An empty family has no member identities with which to match it.
            match = matching_families.get(signature) if father or mother or children else None
            if match is None:
                match = len(merged_families)
                matching_families[signature] = match
                merged_families.append((father, mother, children, role))
                family_sources.append([])
            family_sources[match].append(f"{label} {reference}")
    return merged_people, merged_families, ["; ".join(sources) for sources in family_sources]


def merge_gedcom_person(records: list[dict], person_id: int) -> dict:
    """Use a recorded name for display and expose alternate names and conflicting years."""
    person = {"id": person_id}
    names = list(dict.fromkeys((record["first"], record["surname"]) for record in records
                               if record["first"] or record["surname"]))
    person["first"], person["surname"] = names[0] if names else ("", "")
    person["surname_group"] = person["surname"] or "Unknown"
    notes = []
    if len(names) > 1:
        notes.append("Recorded names: " + "; ".join(" ".join(filter(None, name)) for name in names))
    for field in ("birth", "death"):
        years = sorted({record[field] for record in records if record[field] is not None})
        person[field] = years[0] if len(years) == 1 else None
        if len(years) > 1:
            notes.append(f"Conflicting {field} years: " + ", ".join(map(str, years)))
    if notes:
        person["merge_note"] = " · ".join(notes)
    return person


def build_data(gedcom: Path | None = None) -> dict:
    """Assemble the profile from the selected source."""
    if gedcom is None:
        return profile_data(load_people(), load_families_with_roles(), [], None)
    return profile_data(*load_gedcom_profile(gedcom), gedcom.name)


def profile_data(
    people: list[dict], families: list[tuple], references: list[str], source_name: str | None,
) -> dict:
    placements = generation_layout(people, families, include_component_generation=True)
    assignment, segments, inconsistencies = compute_segments(people, families, placements)

    by_id = {person["id"]: person for person in people}
    out_people = [
        {
            "id": person["id"],
            "first": person["first"],
            "surname": person["surname"],
            "group": person["surname_group"],
            "generation": placements[person["id"]]["generation"],
            "component": placements[person["id"]]["component"],
            "component_generation": placements[person["id"]]["component_generation"],
            "birth": person["birth"],
            "death": person["death"],
            "segment": assignment.get(person["id"]),
            "alignment": placements[person["id"]]["alignment"],
            **({"merge_note": person["merge_note"], "reference": person["reference"]}
               if "merge_note" in person else {}),
        }
        for person in people
    ]

    roles = Counter(role for _, _, _, role in families)
    decades: dict[str, int] = {}
    for person in out_people:
        if person["birth"] is not None:
            decade = (person["birth"] // 10) * 10
            key = f"{decade}s"
            decades[key] = decades.get(key, 0) + 1

    return {
        "gedcom": source_name,
        "people": out_people,
        "segments": segments,
        "families": [
            {
                "id": family_id,
                "parents": [parent for parent in (father, mother) if parent is not None],
                "children": children,
                "role": role,
                **({"reference": references[family_id - 1]} if references else {}),
            }
            for family_id, (father, mother, children, role) in enumerate(families, 1)
        ],
        "stats": {
            "people": len(out_people),
            "families": len(families),
            "main_line": roles.get("main_line", 0),
            "collateral": roles.get("collateral", 0),
            "spouse_ancestry": roles.get("spouse_ancestry", 0),
            "generations": max(p["generation"] for p in out_people) if out_people else 0,
            "groups": len({p["group"] for p in out_people}),
            "dated": sum(1 for p in out_people if p["birth"] is not None),
            "main_line_people": len(assignment),
        },
        "gaps": {
            "conflicting": sum(1 for p in out_people if p["alignment"] == "conflict"),
            "undated": sum(1 for p in out_people if p["birth"] is None),
            "unaligned": sum(1 for p in out_people if p["generation"] == 0),
            "inconsistencies": [
                {
                    **item,
                    "name": f"{by_id[item['person']]['first']} {by_id[item['person']]['surname']}".strip(),
                }
                for item in inconsistencies
            ],
        },
        "birth_decades": decades,
    }


def gedcom_graph_data(
    people: list[dict], families: list[tuple], references: list[str],
) -> dict[str, list[dict[str, str]]]:
    """Adapt GEDCOM members to the graph's person and family fields."""
    graph_people = [
        {
            "id": str(person["id"]),
            "first_name": person["first"],
            "surname": person["surname"],
            "birth_year": "" if person["birth"] is None else str(person["birth"]),
            "death_year": "" if person["death"] is None else str(person["death"]),
            "reference": person["reference"],
            **({"note": person["merge_note"]} if "merge_note" in person else {}),
        }
        for person in people
    ]
    graph_families = [
        {
            "id": str(family_id),
            "father_id": str(father) if father is not None else "",
            "mother_id": str(mother) if mother is not None else "",
            "children_ids": ";".join(map(str, children)),
            "branch_role": "",
            "reference": reference,
        }
        for family_id, ((father, mother, children, _), reference) in enumerate(
            zip(families, references, strict=True), 1
        )
    ]
    add_family_generations(graph_people, graph_families)
    return {"people": graph_people, "families": graph_families, "evidence": [], "sources": []}


def render_html(payload: str, graph_html: str) -> str:
    """Embed the profile and both tree viewers in a self-contained page."""
    graph_payload = json.dumps(graph_html, ensure_ascii=False).replace("<", "\\u003c")
    template = TEMPLATE.read_text(encoding="utf-8")
    before, after = template.split("__PROFILE_DATA__", 1)
    after = after.replace("__GENERATION_LAYERS_JS__", LAYERS_SCRIPT.read_text(encoding="utf-8"), 1)
    return before.replace("__PROFILE_GRAPH__", graph_payload, 1) + payload + after


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", metavar="FILE", type=Path, nargs="*", help="UTF-8 GEDCOM inputs")
    parser.add_argument("--gedcom", type=Path, nargs="+", action="extend", default=[],
                        help="One or more UTF-8 GEDCOM inputs")
    parser.add_argument("--output", type=Path, help="Destination HTML path")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML in the default browser")
    args = parser.parse_args()
    inputs = list(dict.fromkeys(path.resolve() for path in [*args.gedcom, *args.files]))
    filename = "merged_family_profile.html" if len(inputs) > 1 else (
        f"{inputs[0].stem}_family_profile.html" if inputs else "family_profile.html"
    )
    output = args.output or ROOT / "artifacts/interactive" / filename
    try:
        if output.exists() and any(output.samefile(path) for path in inputs if path.exists()):
            parser.error("--output must differ from every input GEDCOM")
        if not inputs:
            profile = build_data()
            graph = render_graph_html(registry_graph_data(), embedded=True)
        else:
            loaded = load_gedcom_profile(inputs[0]) if len(inputs) == 1 else merge_gedcom_profiles(inputs)
            source_name = ", ".join(path.name for path in inputs)
            profile = profile_data(*loaded, source_name)
            graph = render_graph_html(
                gedcom_graph_data(*loaded), embedded=True, source_name=source_name
            )
        payload = json.dumps(profile, ensure_ascii=False).replace("<", "\\u003c")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_html(payload, graph), encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(f"Wrote {output}")
    if args.open and not webbrowser.open(output.resolve().as_uri()):
        parser.exit(1, f"{parser.prog}: Could not open {output} in a browser\n")


if __name__ == "__main__":
    main()
