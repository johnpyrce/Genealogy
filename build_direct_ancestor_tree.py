"""Extract and render the direct ancestors of Tadeusz (Ted) Pyrc/Pyrce."""

from __future__ import annotations

import csv
import html
import shutil
import subprocess
import tempfile
from collections import defaultdict, deque
from pathlib import Path

from genealogy_data import DIRECTORY, load_relationship_evidence, load_sources


PEOPLE_REGISTRY = DIRECTORY / "genealogy_people_registry.csv"
FAMILY_REGISTRY = DIRECTORY / "genealogy_family_registry.csv"
CSV_OUTPUT = DIRECTORY / "tadeusz_pyrc_direct_ancestors.csv"
SVG_OUTPUT = DIRECTORY / "tadeusz_pyrc_ancestor_tree.svg"
PNG_OUTPUT = DIRECTORY / "tadeusz_pyrc_ancestor_tree.png"
REPORT_OUTPUT = DIRECTORY / "tadeusz_pyrc_ancestor_report.md"

ANCHOR_ID = 81
ANCHOR_ALIASES = "Tadeusz Pyrc; Ted Pyrc; Tadeusz Pyrce; Ted Pyrce"

NODE_WIDTH = 240
NODE_HEIGHT = 116
LEAF_GAP = 32
ROW_GAP = 116
MARGIN_X = 70
HEADER_HEIGHT = 142


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def display_name(person: dict[str, str]) -> str:
    surname = "" if person["surname"] == "Unknown" else f" {person['surname']}"
    return f"{person['first_name']}{surname}"


def confidence_rank(value: str) -> int:
    return {"confirmed": 2, "probable": 1, "uncertain": 0}.get(value, -1)


def evidence_for_family(
    family_id: int, evidence: list[dict[str, str]]
) -> list[dict[str, str]]:
    return [row for row in evidence if int(row["family_id"]) == family_id]


def evidence_for_parent_link(
    family_id: int,
    parent_id: int,
    child_id: int,
    evidence: list[dict[str, str]],
) -> list[dict[str, str]]:
    family_rows = evidence_for_family(family_id, evidence)
    specific_rows = [
        row for row in family_rows
        if row["relationship"] == "parent-child"
        and row["person_id"] == str(parent_id)
        and row["related_person_id"] == str(child_id)
    ]
    return specific_rows or [row for row in family_rows if row["relationship"] == "family"]


def build_ancestry(
    people: dict[int, dict[str, str]],
    families: dict[int, dict[str, str]],
) -> tuple[dict[int, int], dict[int, list[tuple[int, int, str]]], list[str]]:
    """Return generations, paths, and structural warnings for the anchor."""
    child_families: dict[int, list[int]] = defaultdict(list)
    for family_id, family in families.items():
        for value in family["children_ids"].split(";"):
            if value:
                child_families[int(value)].append(family_id)

    generations = {ANCHOR_ID: 0}
    # Each path contains (person_id, family_id used to reach parent, parent role).
    paths: dict[int, list[tuple[int, int, str]]] = {ANCHOR_ID: []}
    warnings: list[str] = []
    queue = deque([ANCHOR_ID])

    while queue:
        child_id = queue.popleft()
        parent_families = child_families.get(child_id, [])
        if len(parent_families) > 1:
            warnings.append(
                f"Person {child_id} ({display_name(people[child_id])}) appears as a child "
                f"in multiple families: {', '.join(map(str, parent_families))}."
            )
        for family_id in parent_families:
            family = families[family_id]
            for role, field in (("father", "father_id"), ("mother", "mother_id")):
                if not family[field]:
                    continue
                parent_id = int(family[field])
                proposed_generation = generations[child_id] + 1
                if parent_id == ANCHOR_ID or proposed_generation > len(people):
                    raise ValueError(f"Cycle detected through person {parent_id}")
                new_path = paths[child_id] + [(parent_id, family_id, role)]
                if parent_id not in generations:
                    generations[parent_id] = proposed_generation
                    paths[parent_id] = new_path
                    queue.append(parent_id)
                elif generations[parent_id] != proposed_generation:
                    warnings.append(
                        f"Pedigree collapse places person {parent_id} in more than one generation."
                    )
    return generations, paths, warnings


def path_text(path: list[tuple[int, int, str]], people: dict[int, dict[str, str]]) -> str:
    names = [display_name(people[ANCHOR_ID])]
    names.extend(display_name(people[person_id]) for person_id, _, _ in path)
    return " ← ".join(names)


def relationship_text(path: list[tuple[int, int, str]]) -> str:
    roles = [role for _, _, role in path]
    if len(roles) == 1:
        return roles[0]
    return "'s ".join(roles)


def source_details(
    family_id: int,
    parent_id: int,
    child_id: int,
    evidence: list[dict[str, str]],
    sources: dict[str, dict[str, str]],
) -> tuple[str, str, str, str, str]:
    rows = evidence_for_parent_link(family_id, parent_id, child_id, evidence)
    source_ids = sorted({row["source_id"] for row in rows})
    chart_names = [sources[source_id]["display_name"] for source_id in source_ids]
    locations = sorted({row["location"] for row in rows if row["location"]})
    evidence_ids = [row["evidence_id"] for row in rows]
    confidences = [row["confidence"] for row in rows]
    confidence = min(confidences, key=confidence_rank) if confidences else "uncited"
    return (
        ";".join(source_ids),
        "; ".join(chart_names),
        "; ".join(locations),
        ";".join(evidence_ids),
        confidence,
    )


def write_csv(
    people: dict[int, dict[str, str]],
    generations: dict[int, int],
    paths: dict[int, list[tuple[int, int, str]]],
    evidence: list[dict[str, str]],
    sources: dict[str, dict[str, str]],
) -> None:
    fieldnames = [
        "person_id", "name", "generation", "relationship_to_tadeusz",
        "path_from_tadeusz", "immediate_descendant_id", "parent_family_id",
        "source_ids", "source_charts", "chart_locations", "evidence_ids",
        "confidence", "birth_year", "death_year", "person_note",
    ]
    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        for person_id in sorted(
            (person_id for person_id in generations if person_id != ANCHOR_ID),
            key=lambda value: (
                generations[value],
                tuple(0 if role == "father" else 1 for _, _, role in paths[value]),
            ),
        ):
            path = paths[person_id]
            _, family_id, _ = path[-1]
            descendant_id = ANCHOR_ID if len(path) == 1 else path[-2][0]
            source_ids, charts, locations, evidence_ids, confidence = source_details(
                family_id, person_id, descendant_id, evidence, sources
            )
            person = people[person_id]
            writer.writerow({
                "person_id": person_id,
                "name": display_name(person),
                "generation": generations[person_id],
                "relationship_to_tadeusz": relationship_text(path),
                "path_from_tadeusz": path_text(path, people),
                "immediate_descendant_id": descendant_id,
                "parent_family_id": family_id,
                "source_ids": source_ids,
                "source_charts": charts,
                "chart_locations": locations,
                "evidence_ids": evidence_ids,
                "confidence": confidence,
                "birth_year": person["birth_year"],
                "death_year": person["death_year"],
                "person_note": person["note"],
            })


def tree_positions(
    generations: dict[int, int], paths: dict[int, list[tuple[int, int, str]]]
) -> tuple[dict[int, float], int]:
    parents: dict[int, list[int]] = defaultdict(list)
    for person_id, path in paths.items():
        if person_id == ANCHOR_ID:
            continue
        child_id = ANCHOR_ID if len(path) == 1 else path[-2][0]
        parents[child_id].append(person_id)
    for child_id in parents:
        parents[child_id].sort(key=lambda parent_id: paths[parent_id][-1][2] != "father")

    x_positions: dict[int, float] = {}
    next_leaf = 0

    def place(person_id: int) -> float:
        nonlocal next_leaf
        if person_id in x_positions:
            return x_positions[person_id]
        parent_ids = parents.get(person_id, [])
        if not parent_ids:
            x_positions[person_id] = MARGIN_X + next_leaf * (NODE_WIDTH + LEAF_GAP)
            next_leaf += 1
        else:
            parent_x = [place(parent_id) for parent_id in parent_ids]
            x_positions[person_id] = sum(parent_x) / len(parent_x)
        return x_positions[person_id]

    place(ANCHOR_ID)
    minimum = min(x_positions.values())
    for person_id in x_positions:
        x_positions[person_id] = x_positions[person_id] - minimum + MARGIN_X
    width = int(max(x_positions.values()) + NODE_WIDTH + MARGIN_X)
    return x_positions, max(generations.values())


def wrap_name(value: str, limit: int = 25) -> list[str]:
    if len(value) <= limit:
        return [value]
    words = value.split()
    pivot = max(1, len(words) // 2)
    return [" ".join(words[:pivot]), " ".join(words[pivot:])]


def write_svg(
    people: dict[int, dict[str, str]],
    families: dict[int, dict[str, str]],
    generations: dict[int, int],
    paths: dict[int, list[tuple[int, int, str]]],
    evidence: list[dict[str, str]],
    sources: dict[str, dict[str, str]],
) -> None:
    positions, max_generation = tree_positions(generations, paths)
    width = max(1120, int(max(positions.values()) + NODE_WIDTH + MARGIN_X))
    height = HEADER_HEIGHT + (max_generation + 1) * NODE_HEIGHT + max_generation * ROW_GAP + 78

    def top_for(person_id: int) -> float:
        return HEADER_HEIGHT + (max_generation - generations[person_id]) * (
            NODE_HEIGHT + ROW_GAP
        )

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<filter id="shadow" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#243b40" flood-opacity="0.16"/></filter>',
        "</defs>",
        '<rect width="100%" height="100%" fill="#f7f4ed"/>',
        '<text x="70" y="52" font-family="Georgia,serif" font-size="34" font-weight="700" fill="#173b3f">Direct ancestors of Tadeusz (Ted) Pyrc / Pyrce</text>',
        '<text x="70" y="84" font-family="Arial,sans-serif" font-size="16" fill="#52666a">Only direct parent-child lines are shown. Older generations are above; labels identify the source chart for each link.</text>',
        '<text x="70" y="110" font-family="Arial,sans-serif" font-size="14" fill="#647477">A chart placement records the claimed parentage; it is not independent genetic proof.</text>',
    ]

    for parent_id, path in sorted(paths.items(), key=lambda item: generations[item[0]], reverse=True):
        if parent_id == ANCHOR_ID:
            continue
        _, family_id, _ = path[-1]
        child_id = ANCHOR_ID if len(path) == 1 else path[-2][0]
        px = positions[parent_id] + NODE_WIDTH / 2
        py = top_for(parent_id) + NODE_HEIGHT
        cx = positions[child_id] + NODE_WIDTH / 2
        cy = top_for(child_id)
        mid_y = (py + cy) / 2
        rows = evidence_for_parent_link(family_id, parent_id, child_id, evidence)
        source_ids = "/".join(sorted({row["source_id"] for row in rows})) or "uncited"
        details = "; ".join(
            f"{row['source_id']} {row['location']}: {row['transcription']} ({row['confidence']})"
            for row in rows
        )
        svg.append(f'<g><title>{html.escape(details)}</title>')
        svg.append(
            f'<path d="M{px:.1f},{py:.1f} C{px:.1f},{mid_y:.1f} {cx:.1f},{mid_y:.1f} {cx:.1f},{cy:.1f}" '
            'fill="none" stroke="#58757b" stroke-width="3.2"/>'
        )
        label_x = (px + cx) / 2
        label_y = mid_y - 4
        svg.append(f'<rect x="{label_x - 35:.1f}" y="{label_y - 14:.1f}" width="70" height="22" rx="11" fill="#f7f4ed"/>')
        svg.append(f'<text x="{label_x:.1f}" y="{label_y + 2:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" font-weight="700" fill="#47646a">{html.escape(source_ids)}</text>')
        svg.append("</g>")

    palette = ["#d8eae5", "#dce7ee", "#eee5d1", "#eadde2", "#e5e2ef", "#f1e1c9"]
    for person_id in sorted(generations, key=lambda value: (generations[value], positions[value])):
        person = people[person_id]
        generation = generations[person_id]
        x = positions[person_id]
        y = top_for(person_id)
        fill = "#c9e5dd" if person_id == ANCHOR_ID else palette[generation % len(palette)]
        border = "#2f716a" if person_id == ANCHOR_ID else "#91aaa8"
        years = ""
        if person["birth_year"] or person["death_year"]:
            years = f"{person['birth_year'] or '?'}–{person['death_year'] or ''}"
        name_lines = wrap_name(display_name(person))
        svg.append("<g>")
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" rx="15" fill="#ffffff" stroke="{border}" stroke-width="1.6" filter="url(#shadow)"/>')
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{NODE_WIDTH}" height="34" rx="15" fill="{fill}"/>')
        svg.append(f'<path d="M{x:.1f},{y + 19:.1f} h{NODE_WIDTH} v15 h-{NODE_WIDTH} z" fill="{fill}"/>')
        svg.append(f'<text x="{x + 14:.1f}" y="{y + 23:.1f}" font-family="Arial,sans-serif" font-size="13" font-weight="700" fill="#173b3f">Generation {generation}</text>')
        for index, line in enumerate(name_lines):
            svg.append(f'<text x="{x + 14:.1f}" y="{y + 58 + index * 20:.1f}" font-family="Arial,sans-serif" font-size="17" font-weight="700" fill="#243b40">{html.escape(line)}</text>')
        detail_y = y + (102 if len(name_lines) == 2 else 87)
        detail = f"ID {person_id}" + (f"  •  {years}" if years else "")
        if person_id == ANCHOR_ID:
            detail = f"ID {person_id}  •  anchor person"
        svg.append(f'<text x="{x + 14:.1f}" y="{detail_y:.1f}" font-family="Arial,sans-serif" font-size="13" fill="#5b6d71">{html.escape(detail)}</text>')
        svg.append("</g>")

    svg.append("</svg>")
    SVG_OUTPUT.write_text("\n".join(svg), encoding="utf-8")

    rasterize_svg(SVG_OUTPUT, PNG_OUTPUT)


def rasterize_svg(svg_path: Path, png_path: Path) -> None:
    """Make a PNG while preserving SVG paths, including relationship links."""
    sips = shutil.which("sips")
    magick = shutil.which("magick")
    if not (sips and magick):
        raise RuntimeError("sips and ImageMagick are required to create the PNG preview")
    with tempfile.TemporaryDirectory(prefix="genealogy-svg-") as temporary_directory:
        transparent_png = Path(temporary_directory) / "transparent.png"
        subprocess.run(
            [sips, "-s", "format", "png", str(svg_path), "--out", str(transparent_png)],
            check=True,
        )
        subprocess.run(
            [
                magick, str(transparent_png), "-background", "#f7f4ed",
                "-alpha", "remove", "-alpha", "off", str(png_path),
            ],
            check=True,
        )


def write_report(
    people: dict[int, dict[str, str]],
    families: dict[int, dict[str, str]],
    generations: dict[int, int],
    paths: dict[int, list[tuple[int, int, str]]],
    evidence: list[dict[str, str]],
    sources: dict[str, dict[str, str]],
    warnings: list[str],
) -> None:
    children_with_parents = {
        int(value)
        for family in families.values()
        if family["father_id"] or family["mother_id"]
        for value in family["children_ids"].split(";") if value
    }
    terminal = [
        person_id for person_id in generations
        if person_id != ANCHOR_ID and person_id not in children_with_parents
    ]
    lines = [
        "# Direct ancestors of Tadeusz (Ted) Pyrc / Pyrce",
        "",
        f"Anchor: **{display_name(people[ANCHOR_ID])} (person {ANCHOR_ID})**. "
        f"Search aliases: {ANCHOR_ALIASES}.",
        "",
        f"The current registries identify **{len(generations) - 1} direct ancestors across "
        f"{max(generations.values())} ancestral generations**. Only parents and their parents "
        "are included; spouses who are not ancestors, siblings, descendants, and collateral "
        "relatives are excluded.",
        "",
        "## Ancestors by generation",
        "",
    ]
    for generation in range(1, max(generations.values()) + 1):
        names = [
            display_name(people[person_id])
            for person_id in generations if generations[person_id] == generation
        ]
        lines.append(f"- **Generation {generation}:** {', '.join(names)}")

    lines.extend(["", "## Where the documented lines currently end", ""])
    for person_id in sorted(terminal, key=lambda value: (generations[value], display_name(people[value]))):
        lines.append(
            f"- {display_name(people[person_id])} (generation {generations[person_id]}): "
            "no parents are recorded in the current family registry."
        )

    lines.extend(["", "## Evidence and limitations", ""])
    used_family_ids = sorted({family_id for path in paths.values() for _, family_id, _ in path})
    for family_id in used_family_ids:
        family = families[family_id]
        father = display_name(people[int(family["father_id"])]) if family["father_id"] else "unknown father"
        mother = display_name(people[int(family["mother_id"])]) if family["mother_id"] else "unknown mother"
        rows = evidence_for_family(family_id, evidence)
        citations = "; ".join(
            f"{row['evidence_id']} — {row['source_id']} ({sources[row['source_id']]['display_name']}), "
            f"{row['location']}, {row['confidence']}"
            for row in rows
        )
        lines.append(f"- Family {family_id}, {father} + {mother}: {citations}")
    lines.extend([
        "",
        "The charts document genealogical claims. Calling these people genetic ancestors assumes "
        "the charted parent-child relationships are biological; the extracted charts alone do not "
        "constitute independent genetic or civil-record proof.",
    ])
    if warnings:
        lines.extend(["", "## Structural warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.extend(["", "No cycles, duplicate parent-family assignments, or generation conflicts were found."])
    REPORT_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    people = {int(row["id"]): row for row in read_rows(PEOPLE_REGISTRY)}
    families = {int(row["id"]): row for row in read_rows(FAMILY_REGISTRY)}
    evidence = load_relationship_evidence()
    sources = load_sources()
    if ANCHOR_ID not in people:
        raise SystemExit(f"Anchor person {ANCHOR_ID} is missing")
    generations, paths, warnings = build_ancestry(people, families)
    write_csv(people, generations, paths, evidence, sources)
    write_svg(people, families, generations, paths, evidence, sources)
    write_report(people, families, generations, paths, evidence, sources, warnings)
    print(
        f"Wrote {len(generations) - 1} ancestors across {max(generations.values())} "
        f"generations to {CSV_OUTPUT.name}, {SVG_OUTPUT.name}, {PNG_OUTPUT.name}, "
        f"and {REPORT_OUTPUT.name}."
    )


if __name__ == "__main__":
    main()
