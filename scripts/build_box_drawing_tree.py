"""Build a connected textual family tree from the CSV registries."""

from __future__ import annotations

from scripts.lib.genealogy_data import (
    ROOT,
    family_branch_roles,
    family_source_ids,
    load_families,
    load_people,
    load_sources,
)


OUTPUT = ROOT / "docs" / "trees" / "family_tree.md"
BRANCH_TITLES = {
    "main_line": "main line",
    "spouse_ancestry": "spouse ancestry",
    "collateral": "collateral",
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


def person_label(person: dict[str, str | int | None]) -> str:
    """Format a person with a stable ID and the recorded name and dates."""
    surname = str(person["surname"])
    name = str(person["first"])
    if surname and surname != "Unknown":
        name += f" {surname}"
    return f"Person {person['id']} · {name}{years(person)}"


def render_tree(
    people: dict[int, dict[str, str | int | None]],
    families: list[tuple[int | None, int | None, list[int], str]],
    roles: dict[int, str],
    sources: dict[int, list[str]],
) -> str:
    """Render every family as a connected, cycle-safe box-drawing forest."""
    families_by_id = {family_id: family for family_id, family in enumerate(families, start=1)}
    parent_families: dict[int, list[int]] = {}
    unions: dict[int, list[int]] = {}
    for family_id, (partner_1, partner_2, children, _) in families_by_id.items():
        for partner_id in (partner_1, partner_2):
            if partner_id is not None:
                unions.setdefault(partner_id, []).append(family_id)
        for child_id in children:
            parent_families.setdefault(child_id, []).append(family_id)

    roots = [
        family_id
        for family_id, (partner_1, partner_2, _, _) in families_by_id.items()
        if not any(
            parent_families.get(partner_id, [])
            for partner_id in (partner_1, partner_2)
            if partner_id is not None
        )
    ]
    traversal_order = roots + [family_id for family_id in families_by_id if family_id not in roots]
    rendered_families: set[int] = set()

    lines = [
        "# Combined Muszyna and Wapienne family tree",
        "",
        "This textual tree is generated directly from the editable people, family, source, and relationship-evidence CSV registries.",
        "",
        "**Notation:** Each family joins its two recorded partner slots to their children. A child's indented family records continue that person's descendants. `↪` points to a family expanded elsewhere; `†` precedes a death-only year. Stable person and family IDs disambiguate repeated names and alternative accounts.",
        "",
        "```text",
    ]

    def family_references(person_id: int, family_id: int, relationship: str) -> str:
        """Point to other family records that contain the same person."""
        if relationship == "partner":
            references = [
                linked_id for linked_id in unions.get(person_id, []) if linked_id != family_id
            ]
            description = "also partner in"
        elif relationship == "parent":
            references = [
                linked_id
                for linked_id in parent_families.get(person_id, [])
                if linked_id != family_id
            ]
            description = "child in"
        else:
            references = [
                linked_id
                for linked_id in parent_families.get(person_id, [])
                if linked_id != family_id
            ]
            description = "also child in"
        if not references:
            return ""
        family_word = "Family" if len(references) == 1 else "Families"
        return f" · ↪ {description} {family_word} {', '.join(map(str, references))}"

    def append_family(family_id: int, prefix: str, connector: str) -> None:
        if family_id in rendered_families:
            lines.append(f"{prefix}{connector} ↪ Family {family_id} (expanded elsewhere)")
            return

        rendered_families.add(family_id)
        partner_1, partner_2, children, note = families_by_id[family_id]
        role = BRANCH_TITLES.get(roles[family_id], roles[family_id])
        source_text = ", ".join(sources.get(family_id, [])) or "none recorded"
        lines.append(f"{prefix}{connector} Family {family_id} · {role} · sources: {source_text}")
        detail_prefix = prefix + ("    " if connector == "└──" else "│   ")
        partner_1_text = (
            person_label(people[partner_1])
            + family_references(partner_1, family_id, "partner")
            + family_references(partner_1, family_id, "parent")
            if partner_1
            else "not recorded"
        )
        partner_2_text = (
            person_label(people[partner_2])
            + family_references(partner_2, family_id, "partner")
            + family_references(partner_2, family_id, "parent")
            if partner_2
            else "not recorded"
        )
        details = [f"Partner 1: {partner_1_text}", f"Partner 2: {partner_2_text}"]
        if note:
            details.append(f"Registry note: {note}")
        details.append("Children:" if children else "Children: none recorded")

        for index, detail in enumerate(details):
            is_last_detail = index == len(details) - 1
            lines.append(f"{detail_prefix}{'└──' if is_last_detail else '├──'} {detail}")

        if not children:
            return

        children_prefix = detail_prefix + "    "
        for child_index, child_id in enumerate(children):
            is_last_child = child_index == len(children) - 1
            child_connector = "└──" if is_last_child else "├──"
            child_text = person_label(people[child_id]) + family_references(
                child_id, family_id, "alternative_parent"
            )
            lines.append(f"{children_prefix}{child_connector} {child_text}")
            descendant_prefix = children_prefix + ("    " if is_last_child else "│   ")
            descendant_families = [
                linked_id for linked_id in unions.get(child_id, []) if linked_id != family_id
            ]
            for family_index, linked_id in enumerate(descendant_families):
                linked_connector = "└──" if family_index == len(descendant_families) - 1 else "├──"
                append_family(linked_id, descendant_prefix, linked_connector)

    component = 0
    for family_id in traversal_order:
        if family_id in rendered_families:
            continue
        component += 1
        if component > 1:
            lines.append("")
        lines.append(f"Tree {component}")
        append_family(family_id, "", "└──")

    used_people = {
        person_id
        for partner_1, partner_2, children, _ in families
        for person_id in (partner_1, partner_2, *children)
        if person_id is not None
    }
    unlinked_people = sorted(
        (person for person_id, person in people.items() if person_id not in used_people),
        key=lambda person: (person["surname_group"], person["first"], person["id"]),
    )
    if unlinked_people:
        lines.extend(["", "People without a recorded family"])
        for index, person in enumerate(unlinked_people):
            connector = "└──" if index == len(unlinked_people) - 1 else "├──"
            note = f" · {person['note']}" if person["note"] else ""
            lines.append(f"{connector} {person_label(person)}{note}")

    lines.extend([
        "```",
        "",
        "This view reports registry records as documented. Blank parents, children, dates, or sources are missing observations, not proof of historical absence. Repeated parentage is preserved as an alternative account rather than resolved silently.",
        "",
    ])
    return "\n".join(lines)


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

    OUTPUT.write_text(render_tree(people, families, roles, sources), encoding="utf-8")
    print(f"Wrote {OUTPUT.name} from {len(people)} people and {len(families)} family records")


if __name__ == "__main__":
    build()
