"""Generate a Cytoscape.js version of the interactive genealogy graph."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from shutil import copyfile

ROOT = Path(__file__).resolve().parents[1]
REGISTRIES = ROOT / "data" / "registries"
OUTPUT = ROOT / "artifacts" / "interactive" / "genealogy_relationship_graph.html"
TEMPLATE = Path(__file__).with_name("templates") / "cytoscape_genealogy_graph.html"
HELP_OUTPUT = OUTPUT.with_name("genealogy_relationship_graph_help.html")
HELP_TEMPLATE = Path(__file__).with_name("templates") / "cytoscape_genealogy_graph_help.html"
HELP_IMAGE = Path(__file__).with_name("templates") / "cytoscape_genealogy_graph_elements.png"


def dataset() -> dict[str, list[dict[str, str]]]:
    """Load the registry tables embedded in the standalone graph page."""
    files = {
        "people": "people.csv",
        "families": "families.csv",
        "evidence": "relationship_evidence.csv",
        "sources": "sources.csv",
    }
    result = {}
    for name, file_name in files.items():
        with (REGISTRIES / file_name).open(encoding="utf-8", newline="") as source:
            result[name] = list(csv.DictReader(source))
    return result


def render_html(data: dict[str, list[dict[str, str]]]) -> str:
    """Embed graph data in the viewer template."""
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__GRAPH_DATA__", payload)
        .replace("__GRAPH_HELP_FILE__", HELP_OUTPUT.name)
    )


def render_help() -> str:
    """Return the companion user guide with a link back to the viewer."""
    return HELP_TEMPLATE.read_text(encoding="utf-8").replace("__GRAPH_FILE__", OUTPUT.name)


def main() -> None:
    OUTPUT.write_text(render_html(dataset()), encoding="utf-8")
    HELP_OUTPUT.write_text(render_help(), encoding="utf-8")
    copyfile(HELP_IMAGE, HELP_OUTPUT.with_name(HELP_IMAGE.name))
    print(f"Wrote {OUTPUT.name}")


if __name__ == "__main__":
    main()
