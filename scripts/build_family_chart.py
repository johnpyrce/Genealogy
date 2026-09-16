"""Generate an HTML family-chart viewer with the registry data embedded."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.lib.genealogy_data import (
    ROOT,
    load_families,
    load_people,
    load_relationship_evidence,
    load_sources,
    person_source_ids,
)

OUTPUT = ROOT / "artifacts" / "interactive" / "family_tree.html"
TEMPLATE = Path(__file__).with_name("templates") / "family_chart.html"


def build_data(people=None, families=None, direct_sources=None) -> list[dict]:
    """Translate registry relationships into reciprocal family-chart links.

    Gender is derived only from explicit father/mother roles. Other people
    remain unknown (U), which family-chart renders with its neutral style.
    """
    using_project_people = people is None
    people = load_people() if using_project_people else people
    families = load_families() if families is None else families
    direct_sources = person_source_ids() if direct_sources is None and using_project_people else (direct_sources or {})
    records = {}
    for person in people:
        person_id = str(person["id"])
        if person_id in records:
            raise ValueError(f"Duplicate person ID: {person_id}")
        records[person_id] = {
            "id": person_id,
            "data": {
                "first name": person["first"], "last name": person["surname"],
                "birthday": str(person["birth"] or ""),
                "death": str(person["death"] or ""), "gender": "U",
                "note": person["note"], "source": person["source"],
                "family name": person.get("surname_group") or person["surname"] or "Unknown",
                "source ids": direct_sources.get(int(person["id"]), []),
                "parentages": [],
            },
            "rels": {"parents": [], "spouses": [], "children": []},
        }
    if not records:
        raise ValueError("The people registry is empty")

    def link(person_id, relation, related_id):
        if person_id == related_id:
            raise ValueError(f"Person {person_id} cannot be their own {relation}")
        links = records[person_id]["rels"][relation]
        if related_id not in links:
            links.append(related_id)

    for father, mother, children, note in families:
        parents = [str(p) for p in (father, mother) if p is not None]
        child_ids = [str(child) for child in children]
        for person_id in parents + child_ids:
            if person_id not in records:
                raise ValueError(f"Family references unknown person ID: {person_id}")
        for parent, gender in ((father, "M"), (mother, "F")):
            if parent is not None:
                data = records[str(parent)]["data"]
                if data["gender"] not in ("U", gender):
                    raise ValueError(f"Conflicting parent roles for person {parent}")
                data["gender"] = gender
        if len(parents) == 2:
            link(parents[0], "spouses", parents[1])
            link(parents[1], "spouses", parents[0])
        for child in child_ids:
            if parents and not any(p["parents"] == parents for p in records[child]["data"]["parentages"]):
                records[child]["data"]["parentages"].append({"parents": parents, "note": note})
            for parent in parents:
                link(parent, "children", child)
                link(child, "parents", parent)

    # A cycle would cause the chart's ancestry traversal to recurse indefinitely.
    visiting, visited = set(), set()

    def visit(person_id):
        if person_id in visiting:
            raise ValueError(f"Ancestry cycle involving person {person_id}")
        if person_id in visited:
            return
        visiting.add(person_id)
        for parent in records[person_id]["rels"]["parents"]:
            visit(parent)
        visiting.remove(person_id)
        visited.add(person_id)

    for person_id in records:
        visit(person_id)
    return list(records.values())


def family_records(families) -> list[dict]:
    """Return JSON-ready family records with stable registry IDs."""
    return [
        {
            "id": str(family_id),
            "parents": [str(value) for value in (father, mother) if value is not None],
            "children": [str(value) for value in children],
            "note": note,
        }
        for family_id, (father, mother, children, note) in enumerate(families, start=1)
    ]


def build_source_views(families, evidence_rows) -> dict[str, list[dict]]:
    """Build source-specific family fragments using the established graph rules."""
    records = family_records(families)
    evidence_by_family: dict[str, list[dict[str, str]]] = {}
    for row in evidence_rows:
        evidence_by_family.setdefault(row["family_id"], []).append(row)

    source_ids = sorted({row["source_id"] for row in evidence_rows})
    views = {source_id: [] for source_id in source_ids}
    for family in records:
        rows = evidence_by_family.get(family["id"], [])
        for source_id in source_ids:
            source_rows = [row for row in rows if row["source_id"] == source_id]
            if not source_rows:
                continue
            if any(row["relationship"] == "family" for row in source_rows):
                fragment = dict(family)
            else:
                has_relationship = any(
                    row["relationship"] in {"spouse", "parent-child"} for row in source_rows
                )
                child_ids = {
                    row["related_person_id"]
                    for row in source_rows
                    if row["relationship"] == "parent-child" and row["related_person_id"]
                }
                fragment = {
                    **family,
                    "parents": family["parents"] if has_relationship else [],
                    "children": [child for child in family["children"] if child in child_ids],
                }
            views[source_id].append(fragment)
    return views


def render_html(
    data: list[dict],
    root_id: str | None = None,
    families=None,
    sources=None,
    evidence_rows=None,
) -> str:
    root_id = root_id or data[0]["id"]
    if root_id not in {person["id"] for person in data}:
        raise ValueError(f"Unknown root person ID: {root_id}")
    family_data = family_records(families) if families is not None else []
    source_data = sorted((sources or {}).values(), key=lambda row: row["source_id"])
    source_views = build_source_views(families, evidence_rows or []) if families is not None else {}
    payload = json.dumps(
        {
            "people": data,
            "families": family_data,
            "sources": source_data,
            "sourceViews": source_views,
            "root": root_id,
        },
        ensure_ascii=False,
    )
    # Prevent registry text from closing the JSON script element.
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return TEMPLATE.read_text(encoding="utf-8").replace("__FAMILY_DATA__", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Destination HTML file")
    parser.add_argument("--root", help="Initial person ID (defaults to the first registry entry)")
    args = parser.parse_args()
    try:
        people = load_people()
        families = load_families()
        data = build_data(people, families, person_source_ids())
        html = render_html(
            data,
            args.root,
            families=families,
            sources=load_sources(),
            evidence_rows=load_relationship_evidence(),
        )
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Wrote {args.output} ({len(data)} people)")


if __name__ == "__main__":
    main()
