"""Build the combined lineage atlas: labeled, dot, and lifeline views in one page.

Placement uses recorded family relationships only, never dates. Generation
assignments reuse scripts.build_generation_overview.generation_layout so this
atlas shares the overview's alignment semantics. Vertical ordering is a
depth-first walk over family unions: partners are placed in adjacent rows and
children follow their parents. All three renderings share this single payload;
the template's switcher alternates between them without losing state.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.build_generation_overview import generation_layout
from scripts.lib.genealogy_data import ROOT, load_families, load_people

TEMPLATE = ROOT / "scripts/templates/generation_atlas_views.html"


def atlas_layout(people: list[dict], families: list[tuple]) -> dict[int, dict]:
    """Assign every person a column (generation) and row (sibling-aware order).

    Rows come from a depth-first walk of family unions sorted by earliest
    generation and lowest member id. Partners land in adjacent rows unless one
    was already placed; children follow their parents. Unaligned people are
    appended afterwards, grouped by connected component, in the final column.
    """
    placements = generation_layout(people, families)
    child_family: dict[int, int] = {}
    person_families: dict[int, list[int]] = {}
    for family_id, (father, mother, children, _) in enumerate(families, 1):
        for child in children:
            child_family.setdefault(child, family_id)
        for parent in (father, mother):
            if parent is not None:
                person_families.setdefault(parent, []).append(family_id)

    order: list[int] = []
    visited_people: set[int] = set()
    visited_families: set[int] = set()

    def place(person_id: int) -> None:
        if person_id not in visited_people:
            visited_people.add(person_id)
            order.append(person_id)

    def walk(family_id: int) -> None:
        if family_id in visited_families:
            return
        visited_families.add(family_id)
        father, mother, children, _ = families[family_id - 1]
        if father is not None:
            place(father)
        if mother is not None:
            place(mother)
        for child in children:
            sub_unions = [f for f in person_families.get(child, []) if f not in visited_families]
            for sub in sub_unions:
                walk(sub)
            place(child)

    def family_key(family_id: int) -> tuple[int, int]:
        father, mother, children, _ = families[family_id - 1]
        members = [m for m in (father, mother, *children) if m is not None]
        generations = [placements[m]["generation"] for m in members]
        return (min(generations), min(members))

    aligned = {p["id"] for p in people if placements[p["id"]]["alignment"] == "aligned"}
    aligned_families = [
        fid for fid, (f, m, _, _) in enumerate(families, 1)
        if f in aligned or m in aligned
    ]
    for family_id in sorted(aligned_families, key=family_key):
        walk(family_id)

    unaligned_families = [
        fid for fid in range(1, len(families) + 1) if fid not in visited_families
    ]
    for family_id in sorted(unaligned_families, key=family_key):
        walk(family_id)
    for person in people:  # safety net: people recorded without any family link
        place(person["id"])

    generations = max((p["generation"] for p in placements.values()), default=0)
    unaligned_col = generations  # zero-based column after the last generation
    layout = {}
    for row, person_id in enumerate(order):
        generation = placements[person_id]["generation"]
        column = generation - 1 if generation else unaligned_col
        layout[person_id] = {
            "column": column,
            "row": row,
            "generation": generation,
            "alignment": placements[person_id]["alignment"],
            "component": placements[person_id]["component"],
        }
    return layout


def build_data() -> dict:
    """Assemble the atlas payload from the registries."""
    registry_people = load_people()
    families = load_families()
    layout = atlas_layout(registry_people, families)
    people = [dict(person, **layout[person["id"]]) for person in registry_people]
    counts = Counter(person["surname_group"] for person in people)
    return {
        "people": people,
        "families": [
            {
                "id": family_id,
                "parents": [p for p in (father, mother) if p is not None],
                "children": children,
            }
            for family_id, (father, mother, children, _) in enumerate(families, 1)
        ],
        "groups": sorted(counts, key=lambda group: (-counts[group], group)),
        "generations": max((p["generation"] for p in people), default=0),
        "columns": max(p["column"] for p in people) + 1 if people else 0,
        "unions": sum(1 for f, m, _, _ in families if f is not None and m is not None),
    }


def render_html(payload: str) -> str:
    """Inject the JSON payload into the combined atlas template."""
    return TEMPLATE.read_text(encoding="utf-8").replace("__ATLAS_DATA__", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts/interactive/generation_atlas_views.html")
    args = parser.parse_args()
    payload = json.dumps(build_data(), ensure_ascii=False).replace("<", "\\u003c")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(payload), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
