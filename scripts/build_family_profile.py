"""Build a standalone family profile app characterizing the family tree.

Two dimensions: time, encoded primarily by generation (to cope with the many
missing dates) and secondarily by recorded birth years; and lineage, encoded
by main-line segments, branches, and spouse ancestry. This generator is fully
separate from the website build chain. It reads the registries by default or
uses a supplied GEDCOM file to write a self-contained HTML artifact.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import webbrowser

from scripts.build_generation_overview import generation_layout
from scripts.import_gedcom import incoming_person, parse_gedcom
from scripts.lib.genealogy_data import FAMILY_REGISTRY, ROOT, load_people, load_registry_csv

TEMPLATE = ROOT / "scripts/templates/family_profile.html"


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


def build_data(gedcom: Path | None = None) -> dict:
    """Assemble the profile from the selected source."""
    if gedcom is None:
        people = load_people()
        families = load_families_with_roles()
        references = []
    else:
        people, families, references = load_gedcom_profile(gedcom)
    placements = generation_layout(people, families)
    assignment, segments, inconsistencies = compute_segments(people, families, placements)

    by_id = {person["id"]: person for person in people}
    out_people = [
        {
            "id": person["id"],
            "first": person["first"],
            "surname": person["surname"],
            "group": person["surname_group"],
            "generation": placements[person["id"]]["generation"],
            "birth": person["birth"],
            "death": person["death"],
            "segment": assignment.get(person["id"]),
            "alignment": placements[person["id"]]["alignment"],
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
        "gedcom": gedcom.name if gedcom is not None else None,
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


def render_html(payload: str) -> str:
    """Inject the JSON payload into the profile template."""
    return TEMPLATE.read_text(encoding="utf-8").replace("__PROFILE_DATA__", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gedcom", type=Path, help="Read people and family links from a UTF-8 GEDCOM file")
    parser.add_argument("--output", type=Path, help="Destination HTML path")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML in the default browser")
    args = parser.parse_args()
    filename = f"{args.gedcom.stem}_family_profile.html" if args.gedcom else "family_profile.html"
    output = args.output or ROOT / "artifacts/interactive" / filename
    try:
        if args.gedcom is not None and output.exists() and output.samefile(args.gedcom):
            parser.error("--output must differ from the input GEDCOM")
        payload = json.dumps(build_data(args.gedcom), ensure_ascii=False).replace("<", "\\u003c")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_html(payload), encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(f"Wrote {output}")
    if args.open and not webbrowser.open(output.resolve().as_uri()):
        parser.exit(1, f"{parser.prog}: Could not open {output} in a browser\n")


if __name__ == "__main__":
    main()
