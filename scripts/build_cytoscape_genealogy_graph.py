"""Generate a Cytoscape.js version of the interactive genealogy graph."""

from __future__ import annotations

import json
import re
from pathlib import Path
from shutil import copyfile

from scripts.lib.genealogy_data import ROOT, REGISTRIES, load_registry_csv

OUTPUT = ROOT / "artifacts" / "interactive" / "genealogy_relationship_graph.html"
TEMPLATE = Path(__file__).with_name("templates") / "cytoscape_genealogy_graph.html"
HELP_OUTPUT = OUTPUT.with_name("genealogy_relationship_graph_help.html")
HELP_TEMPLATE = Path(__file__).with_name("templates") / "cytoscape_genealogy_graph_help.html"
HELP_IMAGE = Path(__file__).with_name("templates") / "cytoscape_genealogy_graph_elements.png"


def add_person_sources(
    people: list[dict[str, str]],
    families: list[dict[str, str]],
    evidence: list[dict[str, str]],
    person_evidence: list[dict[str, str]],
) -> None:
    """Collect explicit person citations and supported family memberships."""
    memberships = {person["id"]: set() for person in people}
    families_by_id = {family["id"]: family for family in families}
    for row in [*person_evidence, *evidence]:
        ids = [row.get("person_id"), row.get("related_person_id")]
        if row.get("relationship") == "family":
            family = families_by_id[row["family_id"]]
            ids.extend([family["father_id"], family["mother_id"], *family["children_ids"].split(";")])
        for person_id in ids:
            if person_id in memberships:
                memberships[person_id].add(row["source_id"])
    for person in people:
        person["source_ids"] = ";".join(sorted(memberships[person["id"]]))


def add_readable_family_evidence(
    evidence: list[dict[str, str]],
    people: list[dict[str, str]],
    person_evidence: list[dict[str, str]],
) -> None:
    """Add display summaries without changing the original source transcriptions."""
    people_by_id = {person["id"]: person for person in people}
    identities = {}
    for row in person_evidence:
        match = re.fullmatch(r"GEDCOM (@[^@]+@)", row["location"])
        if match:
            identities.setdefault((row["source_id"], match[1]), set()).add(row["person_id"])
    for row in evidence:
        lines = row["transcription"].splitlines()
        if not lines or not re.fullmatch(r"0 @[^@]+@ FAM", lines[0]):
            continue
        summary = []
        for line in lines[1:]:
            match = re.fullmatch(r"1 (HUSB|WIFE|CHIL) (@[^@]+@)", line)
            if not match:
                continue
            role, reference = match.groups()
            ids = identities.get((row["source_id"], reference), set())
            person = people_by_id.get(next(iter(ids))) if len(ids) == 1 else None
            name = " ".join(filter(None, [person["first_name"], person["surname"]])) if person else ""
            label = {"HUSB": "Husband", "WIFE": "Wife", "CHIL": "Child"}[role]
            summary.append(f"{label}: {name or 'Unresolved person ' + reference}")
        if summary:
            row["summary"] = "\n".join(summary)


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
        result[name] = load_registry_csv(REGISTRIES / file_name)[1]
    person_evidence = load_registry_csv(REGISTRIES / "person_source_evidence.csv")[1]
    add_readable_family_evidence(result["evidence"], result["people"], person_evidence)
    add_person_sources(result["people"], result["families"], result["evidence"], person_evidence)
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
