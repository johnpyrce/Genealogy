"""Build a family-to-family graph from the reconciled genealogy registry."""

from __future__ import annotations

import csv
import html
import shutil
import subprocess
import tempfile
import textwrap
from collections import defaultdict, deque
from pathlib import Path

from genealogy_data import (
    family_branch_roles,
    family_source_ids,
    load_families,
    load_sources,
)


DIRECTORY = Path(__file__).resolve().parent
REGISTRY = DIRECTORY / "genealogy_people_registry.csv"
SVG_OUTPUT = DIRECTORY / "family_graph.svg"
PNG_OUTPUT = DIRECTORY / "family_graph.png"
PRIMARY_SVG_OUTPUT = DIRECTORY / "family_graph_primary.svg"
PRIMARY_PNG_OUTPUT = DIRECTORY / "family_graph_primary.png"
COMPLETE_SVG_OUTPUT = DIRECTORY / "family_graph_complete.svg"
COMPLETE_PNG_OUTPUT = DIRECTORY / "family_graph_complete.png"

NODE_WIDTH = 390
LINE_HEIGHT = 21
NODE_GAP_X = 64
NODE_GAP_Y = 82
PAGE_MARGIN = 70


def load_people() -> dict[int, dict[str, str]]:
    with REGISTRY.open(encoding="utf-8", newline="") as source:
        return {int(row["id"]): row for row in csv.DictReader(source)}


def name(person: dict[str, str]) -> str:
    surname = "" if person["surname"] == "Unknown" else f" {person['surname']}"
    return f"{person['first_name']}{surname}"


def mother_name(person: dict[str, str]) -> str:
    if person["surname"] == "Unknown":
        return person["first_name"]
    return f"{person['first_name']} née {person['surname']}"


def node_lines(
    family: tuple,
    people: dict[int, dict[str, str]],
    source_ids: list[str],
    branch_role: str,
) -> list[str]:
    father, mother, children, _ = family
    parent_count = int(father is not None) + int(mother is not None)
    lines = [
        f"Father: {name(people[father]) if father else 'not recorded'}",
        f"Mother: {mother_name(people[mother]) if mother else 'not recorded'}",
        f"{parent_count + len(children)} people",
        f"Branch: {branch_role.replace('_', ' ')}",
        f"Sources: {', '.join(source_ids) or 'not assigned'}",
    ]
    if children:
        child_names = ", ".join(name(people[child]) for child in children)
        wrapped = textwrap.wrap(
            f"Children: {child_names}", width=45, subsequent_indent="          ",
            break_long_words=False,
        )
        lines.extend(wrapped)
    else:
        lines.append("Children: none recorded")
    return lines


def person_lines(person: dict[str, str], source_ids: list[str]) -> list[str]:
    years = ""
    if person["birth_year"] or person["death_year"]:
        years = f"Years: {person['birth_year'] or '?'}–{person['death_year'] or ''}"
    lines = ["Individual", "No spouse or children recorded", f"Sources: {', '.join(source_ids) or 'not assigned'}"]
    if years:
        lines.append(years)
    return lines


def build_graph(include_roles: set[str]):
    family_records = load_families()
    role_map = family_branch_roles()
    # A family node requires two recorded spouses. One-parent records are omitted.
    families = {
        index: family for index, family in enumerate(family_records, start=1)
        if (family[0] is not None or family[1] is not None)
        and role_map[index] in include_roles
    }
    spouse_family: dict[int, list[int]] = defaultdict(list)
    for family_id, (father, mother, _, _) in families.items():
        if father is not None:
            spouse_family[father].append(family_id)
        if mother is not None:
            spouse_family[mother].append(family_id)

    included_records = [
        family for index, family in enumerate(family_records, start=1)
        if role_map[index] in include_roles
    ]
    people_with_children = {
        parent for father, mother, children, _ in included_records if children
        for parent in (father, mother) if parent is not None
    }

    edges: list[tuple[int, int, int]] = []
    leaf_people: set[int] = set()
    for parent_id, (_, _, children, _) in families.items():
        for child in children:
            child_families = spouse_family.get(child, [])
            for child_family_id in child_families:
                if child_family_id != parent_id:
                    edges.append((parent_id, child_family_id, child))
            if not child_families and child not in people_with_children:
                leaf_people.add(child)
                edges.append((parent_id, -child, child))
    return families, edges, leaf_people


def connected_components(nodes: set[int], edges: list[tuple[int, int, int]]) -> list[set[int]]:
    adjacent: dict[int, set[int]] = defaultdict(set)
    for source, target, _ in edges:
        adjacent[source].add(target)
        adjacent[target].add(source)
    components = []
    unseen = set(nodes)
    while unseen:
        start = min(unseen)
        component = set()
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in component:
                continue
            component.add(node)
            unseen.discard(node)
            queue.extend(adjacent[node] - component)
        components.append(component)
    return sorted(components, key=lambda c: (-len(c), min(c)))


def family_title(family: tuple, people: dict[int, dict[str, str]]) -> str:
    father, mother, _, _ = family
    def label(person_id: int | None) -> str:
        if person_id is None:
            return "unknown parent"
        person = people[person_id]
        return person["surname"] if person["surname"] != "Unknown" else person["first_name"]

    return f"{label(father)} + {label(mother)}"


def node_source_ids(
    node_id: int, source_map: dict[int, list[str]], edges: list[tuple[int, int, int]]
) -> list[str]:
    if node_id > 0:
        return source_map.get(node_id, [])
    inherited = {
        source_id
        for parent_id, target_id, _ in edges if target_id == node_id
        for source_id in source_map.get(parent_id, [])
    }
    return sorted(inherited)


def render(
    svg_output: Path,
    png_output: Path,
    include_roles: set[str],
    diagram_title: str,
) -> tuple[int, int, int, int]:
    people = load_people()
    families, edges, leaf_people = build_graph(include_roles)
    role_map = family_branch_roles()
    source_map = family_source_ids()
    sources = load_sources()
    edge_nodes = {node for source, target, _ in edges for node in (source, target)}
    connected = connected_components(edge_nodes, edges) if edge_nodes else []
    isolated = sorted(set(families) - edge_nodes)

    # Keep the oldest documented Gościński parents at the visual starting point.
    # Their descendant chain cannot be drawn as a family-to-family arrow because
    # the spouse of their son Wawrzyniec is not identified in the source.
    oldest_family = 1 if 1 in isolated else None
    if oldest_family:
        isolated.remove(oldest_family)

    boxes: dict[int, tuple[float, float, float, float]] = {}
    y_cursor = 150.0
    max_width = 0.0

    if oldest_family:
        lines = node_lines(
            families[oldest_family], people, source_map.get(oldest_family, []),
            role_map[oldest_family],
        )
        height = 62 + len(lines) * LINE_HEIGHT
        boxes[oldest_family] = (PAGE_MARGIN, y_cursor, NODE_WIDTH, height)
        max_width = max(max_width, NODE_WIDTH + 2 * PAGE_MARGIN)
        y_cursor += height + 125

    # Lay out each connected family group in generation rows.
    for component in connected:
        incoming = defaultdict(int)
        outgoing = defaultdict(list)
        for source, target, _ in edges:
            if source in component and target in component:
                incoming[target] += 1
                outgoing[source].append(target)
        roots = sorted(node for node in component if incoming[node] == 0) or [min(component)]
        depth = {node: 0 for node in roots}
        queue = deque(roots)
        while queue:
            source = queue.popleft()
            for target in outgoing[source]:
                proposed = depth[source] + 1
                if proposed > depth.get(target, -1):
                    depth[target] = proposed
                    queue.append(target)
        for node in component:
            depth.setdefault(node, 0)
        ranks: dict[int, list[int]] = defaultdict(list)
        for node in component:
            ranks[depth[node]].append(node)
        component_height = 0.0
        for rank, nodes in sorted(ranks.items()):
            nodes.sort()
            widths = len(nodes) * NODE_WIDTH + (len(nodes) - 1) * NODE_GAP_X
            max_width = max(max_width, widths + 2 * PAGE_MARGIN)
            for column, node in enumerate(nodes):
                lines = (
                    person_lines(people[-node], node_source_ids(node, source_map, edges)) if node < 0
                    else node_lines(
                        families[node], people, source_map.get(node, []), role_map[node]
                    )
                )
                height = 62 + len(lines) * LINE_HEIGHT
                x = PAGE_MARGIN + column * (NODE_WIDTH + NODE_GAP_X)
                y = y_cursor + rank * 245
                boxes[node] = (x, y, NODE_WIDTH, height)
                component_height = max(component_height, rank * 245 + height)
        y_cursor += component_height + 120

    # Families that are not linked to another recorded married child are still shown.
    if isolated:
        y_cursor += 70
        columns = 3
        max_width = max(max_width, columns * NODE_WIDTH + (columns - 1) * NODE_GAP_X + 2 * PAGE_MARGIN)
        row_heights: dict[int, float] = defaultdict(float)
        line_cache = {
            node: node_lines(
                families[node], people, source_map.get(node, []), role_map[node]
            )
            for node in isolated
        }
        for index, node in enumerate(isolated):
            row = index // columns
            row_heights[row] = max(row_heights[row], 62 + len(line_cache[node]) * LINE_HEIGHT)
        row_y = {}
        cursor = y_cursor
        for row in range((len(isolated) + columns - 1) // columns):
            row_y[row] = cursor
            cursor += row_heights[row] + 42
        for index, node in enumerate(isolated):
            row, column = divmod(index, columns)
            boxes[node] = (
                PAGE_MARGIN + column * (NODE_WIDTH + NODE_GAP_X), row_y[row],
                NODE_WIDTH, 62 + len(line_cache[node]) * LINE_HEIGHT,
            )
        y_cursor = cursor

    width = int(max(max_width, 1100))
    height = int(y_cursor + PAGE_MARGIN)
    legend = (
        "Gold nodes and dashed links identify spouse ancestry; gray nodes and dotted links are collateral families."
        if "spouse_ancestry" in include_roles
        else "This concise view includes only families classified as the primary line."
    )
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#718096"/></marker>',
        '<filter id="shadow" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#1f2937" flood-opacity="0.16"/></filter>',
        "</defs>",
        '<rect width="100%" height="100%" fill="#f7f4ed"/>',
        f'<text x="70" y="60" font-family="Georgia,serif" font-size="34" font-weight="700" fill="#173b3f">{html.escape(diagram_title)}</text>',
        '<text x="70" y="94" font-family="Arial,sans-serif" font-size="16" fill="#52666a">Family nodes show couples and children; leaf nodes show children with no recorded spouse or descendants. Arrows identify the child.</text>',
        f'<text x="70" y="119" font-family="Arial,sans-serif" font-size="15" fill="#647477">{html.escape(legend)}</text>',
    ]

    if oldest_family:
        _, oldest_y, _, oldest_h = boxes[oldest_family]
        note_y = oldest_y + oldest_h + 30
        svg.append(f'<text x="70" y="{note_y:.1f}" font-family="Arial,sans-serif" font-size="14" font-style="italic" fill="#647477">Oldest recorded parents. The next family link is not drawn because their son Wawrzyniec\u2019s spouse is unidentified.</text>')

    # Edges sit behind the nodes.
    for source, target, child in edges:
        sx, sy, sw, sh = boxes[source]
        tx, ty, tw, _ = boxes[target]
        x1, y1 = sx + sw / 2, sy + sh
        x2, y2 = tx + tw / 2, ty
        mid_y = (y1 + y2) / 2
        path = f"M{x1:.1f},{y1:.1f} C{x1:.1f},{mid_y:.1f} {x2:.1f},{mid_y:.1f} {x2:.1f},{y2:.1f}"
        label = html.escape(name(people[child]))
        label_x, label_y = (x1 + x2) / 2, mid_y - 7
        edge_role = role_map.get(source, "main_line")
        dash = (
            ' stroke-dasharray="8 6"' if edge_role == "spouse_ancestry"
            else ' stroke-dasharray="3 5"' if edge_role == "collateral"
            else ""
        )
        svg.append(f'<path d="{path}" fill="none" stroke="#718096" stroke-width="2.2"{dash} marker-end="url(#arrow)"/>')
        svg.append(f'<rect x="{label_x - 92:.1f}" y="{label_y - 15:.1f}" width="184" height="24" rx="12" fill="#f7f4ed"/>')
        svg.append(f'<text x="{label_x:.1f}" y="{label_y + 3:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="14" font-weight="700" fill="#355f64">{label}</text>')

    if isolated:
        section_y = min(boxes[node][1] for node in isolated) - 36
        svg.append(f'<text x="70" y="{section_y:.1f}" font-family="Arial,sans-serif" font-size="22" font-weight="700" fill="#355f64">Other recorded families</text>')

    for node_id, (x, y, w, h) in boxes.items():
        is_person = node_id < 0
        lines = (
            person_lines(people[-node_id], node_source_ids(node_id, source_map, edges)) if is_person
            else node_lines(
                families[node_id], people, source_map.get(node_id, []), role_map[node_id]
            )
        )
        node_role = "individual" if is_person else role_map[node_id]
        border = {
            "individual": "#b8b7ce", "main_line": "#aac1bd",
            "spouse_ancestry": "#d4b77b", "collateral": "#aeb9c2",
        }[node_role]
        header = {
            "individual": "#e8e5f2", "main_line": "#dbece6",
            "spouse_ancestry": "#f3e6c9", "collateral": "#e4e9ed",
        }[node_role]
        cited_ids = node_source_ids(node_id, source_map, edges)
        cited_sources = "; ".join(
            f"{source_id}: {sources[source_id]['display_name']} ({sources[source_id]['file_name']})"
            for source_id in cited_ids if source_id in sources
        )
        svg.append(f"<g><title>{html.escape(cited_sources)}</title>")
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="#ffffff" stroke="{border}" stroke-width="1.5" filter="url(#shadow)"/>')
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="42" rx="16" fill="{header}"/>')
        svg.append(f'<path d="M{x},{y + 26} h{w} v16 h{-w} z" fill="{header}"/>')
        title = html.escape(
            name(people[-node_id]) if is_person
            else family_title(families[node_id], people)
        )
        svg.append(f'<text x="{x + 18}" y="{y + 28}" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="#173b3f">{title}</text>')
        for line_index, line in enumerate(lines):
            weight = "700" if not is_person and line_index == 2 else "400"
            color = "#0f766e" if not is_person and line_index == 2 else "#273e42"
            svg.append(f'<text x="{x + 18}" y="{y + 68 + line_index * LINE_HEIGHT}" font-family="Arial,sans-serif" font-size="15" font-weight="{weight}" fill="{color}">{html.escape(line)}</text>')
        svg.append("</g>")

    svg.append("</svg>")
    svg_output.write_text("\n".join(svg), encoding="utf-8")
    rasterize_svg(svg_output, png_output)
    return len(families), len(leaf_people), len(edges), len(isolated)


def rasterize_svg(svg_path: Path, png_path: Path) -> None:
    """Make a PNG while preserving SVG paths, including relationship links."""
    sips = shutil.which("sips")
    magick = shutil.which("magick")
    if not (sips and magick):
        raise RuntimeError("sips and ImageMagick are required to create the PNG outputs")
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


if __name__ == "__main__":
    primary_counts = render(
        PRIMARY_SVG_OUTPUT, PRIMARY_PNG_OUTPUT, {"main_line"},
        "Primary families in the Muszyna family history",
    )
    complete_counts = render(
        COMPLETE_SVG_OUTPUT, COMPLETE_PNG_OUTPUT,
        {"main_line", "spouse_ancestry", "collateral"},
        "Complete families and spouse ancestry",
    )
    shutil.copyfile(PRIMARY_SVG_OUTPUT, SVG_OUTPUT)
    shutil.copyfile(PRIMARY_PNG_OUTPUT, PNG_OUTPUT)
    print(
        "Rendered primary graph "
        f"({primary_counts[0]} families, {primary_counts[1]} individual leaves, {primary_counts[2]} links) "
        "and complete graph "
        f"({complete_counts[0]} families, {complete_counts[1]} individual leaves, {complete_counts[2]} links)."
    )
