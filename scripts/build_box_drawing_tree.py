"""Build the box-drawing family tree directly from the CSV registries."""

from __future__ import annotations

from pathlib import Path

from scripts.lib.genealogy_data import ROOT, family_branch_roles, family_source_ids, load_families, load_people, load_sources


OUTPUT = ROOT / "docs" / "trees" / "merged_family_tree_box_drawing.md"
BRANCH_ORDER = ("main_line", "spouse_ancestry", "collateral")
BRANCH_TITLES = {
    "main_line": "Main line",
    "spouse_ancestry": "Spouse ancestry",
    "collateral": "Collateral families",
}


def years(person: dict[str, str | int | None]) -> str:
    """Return the recorded year range without implying missing dates."""
    birth, death = person["birth"], person["death"]
    if birth is not None and death is not None:
        return f" ({birth}–{death})"
    if birth is not None:
        return f" ({birth})"
    if death is not None:
        return f" (†{death})"
    return ""


def person_name(person: dict[str, str | int | None]) -> str:
    """Format people consistently while retaining the recorded surname."""
    surname = str(person["surname"])
    name = str(person["first"])
    if surname and surname != "Unknown":
        name += f" {surname}"
    return name + years(person)


def append_family(
    lines: list[str],
    family_id: int,
    family: tuple[int | None, int | None, list[int], str],
    people: dict[int, dict[str, str | int | None]],
    source_ids: list[str],
    is_last: bool,
) -> None:
    """Append one registry family as a readable box-drawing branch."""
    father, mother, children, note = family
    connector = "└──" if is_last else "├──"
    prefix = "    " if is_last else "│   "
    sources = ", ".join(source_ids) if source_ids else "none recorded"
    lines.append(f"{connector} Family {family_id} · sources: {sources}")

    details = [
        f"Partner 1: {person_name(people[father]) if father else 'not recorded'}",
        f"Partner 2: {person_name(people[mother]) if mother else 'not recorded'}",
    ]
    if note:
        details.append(f"Registry note: {note}")
    details.append("Children:" if children else "Children: none recorded")

    for index, detail in enumerate(details):
        last_detail = index == len(details) - 1
        lines.append(f"{prefix}{'└──' if last_detail else '├──'} {detail}")

    if children:
        child_prefix = prefix + "    "
        for index, child_id in enumerate(children):
            child_connector = "└──" if index == len(children) - 1 else "├──"
            lines.append(f"{child_prefix}{child_connector} {person_name(people[child_id])}")


def build() -> None:
    """Write a direct, reproducible Markdown view of the family registries."""
    people = {person["id"]: person for person in load_people()}
    families = load_families()
    roles = family_branch_roles()
    sources = family_source_ids()
    source_catalog = load_sources()
    unknown_sources = sorted({source_id for ids in sources.values() for source_id in ids} - set(source_catalog))
    if unknown_sources:
        raise ValueError(f"Family evidence references unknown source IDs: {', '.join(unknown_sources)}")
    used_people = {
        person_id
        for father, mother, children, _ in families
        for person_id in (father, mother, *children)
        if person_id is not None
    }

    lines = [
        "# Combined Muszyna and Wapienne family tree",
        "",
        "This box-drawing view is generated directly from the editable people, family, source, and relationship-evidence CSV registries.",
        "",
        "**Notation:** `†` precedes a death-only year; source IDs identify the chart evidence linked to each family record. Partner labels preserve the two partner slots in the family registry without inferring gender.",
        "",
    ]

    for role in BRANCH_ORDER:
        family_rows = [
            (family_id, family)
            for family_id, family in enumerate(families, start=1)
            if roles[family_id] == role
        ]
        if not family_rows:
            continue
        lines.extend([f"## {BRANCH_TITLES[role]}", "", "```text"])
        for index, (family_id, family) in enumerate(family_rows):
            append_family(lines, family_id, family, people, sources.get(family_id, []), index == len(family_rows) - 1)
        lines.extend(["```", ""])

    unlinked_people = sorted(
        (person for person_id, person in people.items() if person_id not in used_people),
        key=lambda person: (person["surname_group"], person["first"], person["id"]),
    )
    if unlinked_people:
        lines.extend(["## People without a recorded family", "", "```text"])
        for index, person in enumerate(unlinked_people):
            connector = "└──" if index == len(unlinked_people) - 1 else "├──"
            note = f" · {person['note']}" if person["note"] else ""
            lines.append(f"{connector} {person_name(person)}{note}")
        lines.extend(["```", ""])

    lines.extend([
        "This view reports registry records as documented. Blank parents, children, dates, or sources are missing observations, not proof of historical absence.",
        "",
    ])
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT.name} from {len(people)} people and {len(families)} family records")


if __name__ == "__main__":
    build()
