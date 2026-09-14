from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
SOURCE = DIRECTORY / "merged_family_tree_outline.md"
OUTPUT = DIRECTORY / "merged_family_tree_box_drawing.md"


@dataclass
class Node:
    text: str
    children: list[Node] = field(default_factory=list)


def clean(text: str) -> str:
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_sections(markdown: str) -> list[tuple[str, list[Node]]]:
    sections: list[tuple[str, list[Node]]] = []
    heading = None
    roots: list[Node] = []
    stack: list[tuple[int, Node]] = []
    last_node: Node | None = None

    def save_section() -> None:
        nonlocal roots
        if heading and roots:
            sections.append((heading, roots))
        roots = []

    for raw_line in markdown.splitlines():
        if raw_line.startswith("## "):
            save_section()
            heading = raw_line[3:].strip()
            stack = []
            last_node = None
            continue
        if raw_line.startswith("### "):
            save_section()
            heading = raw_line[4:].strip()
            stack = []
            last_node = None
            continue
        match = re.match(r"^(\s*)-\s+(.*)$", raw_line)
        if match and heading:
            indent = len(match.group(1))
            node = Node(clean(match.group(2)))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if stack:
                stack[-1][1].children.append(node)
            else:
                roots.append(node)
            stack.append((indent, node))
            last_node = node
            continue
        if heading and last_node and raw_line.startswith(" ") and raw_line.strip():
            last_node.text = clean(f"{last_node.text} {raw_line.strip()}")

    save_section()
    return sections


def render_node(node: Node, prefix: str, is_last: bool, width: int = 112) -> list[str]:
    connector = "└── " if is_last else "├── "
    continuation = prefix + ("    " if is_last else "│   ")
    available = max(34, width - len(prefix) - len(connector))
    wrapped = textwrap.wrap(node.text, width=available, break_long_words=False) or [""]
    lines = [prefix + connector + wrapped[0]]
    lines.extend(continuation + part for part in wrapped[1:])
    child_prefix = continuation
    for index, child in enumerate(node.children):
        lines.extend(render_node(child, child_prefix, index == len(node.children) - 1, width))
    return lines


def build() -> None:
    sections = parse_sections(SOURCE.read_text(encoding="utf-8"))
    output = [
        "# Combined Muszyna and Wapienne family tree",
        "",
        "This is the box-drawing edition of the consolidated family outline.",
        "",
        (
            "**Notation:** `m.` = married; `née` = maiden name; `†` = marked deceased; "
            "`[P]` = printed chart only; `[H]` = later handwritten chart; "
            "`[?]` = uncertain reading or relationship."
        ),
        "",
    ]
    for title, roots in sections:
        output.extend([f"## {title}", "", "```text"])
        for index, root in enumerate(roots):
            output.extend(render_node(root, "", index == len(roots) - 1))
        output.extend(["```", ""])
    output.extend(
        [
            (
                "The connectors reproduce the relationships recorded in the merged outline. "
                "They do not resolve the source conflicts marked with `[?]`."
            ),
            "",
        ]
    )
    OUTPUT.write_text("\n".join(output), encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(sections)} sections")


if __name__ == "__main__":
    build()
