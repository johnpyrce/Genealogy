"""Validate people, families, sources, and relationship provenance."""

from __future__ import annotations

import csv
from pathlib import Path

from genealogy_data import (
    DIRECTORY,
    load_families,
    load_relationship_evidence,
    load_sources,
)


PEOPLE_REGISTRY = DIRECTORY / "genealogy_people_registry.csv"
CONFIDENCE_VALUES = {"confirmed", "probable", "uncertain"}
RELATIONSHIP_VALUES = {"family", "spouse", "parent-child"}
BRANCH_ROLE_VALUES = {"main_line", "spouse_ancestry", "collateral"}


def main() -> None:
    with PEOPLE_REGISTRY.open(encoding="utf-8", newline="") as source:
        person_rows = list(csv.DictReader(source))
    people = {int(row["id"]): row for row in person_rows}
    families = load_families()
    with (DIRECTORY / "genealogy_family_registry.csv").open(encoding="utf-8", newline="") as source:
        family_rows = list(csv.DictReader(source))
    sources = load_sources()
    evidence_rows = load_relationship_evidence()
    errors = []

    if len(people) != len(person_rows):
        errors.append("People registry contains duplicate IDs")
    evidence_ids = [row["evidence_id"] for row in evidence_rows]
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("Relationship evidence contains duplicate evidence IDs")

    for family_id, (father, mother, children, _) in enumerate(families, start=1):
        if int(family_rows[family_id - 1]["id"]) != family_id:
            errors.append(f"Family row {family_id}: ID is not sequential")
        if family_rows[family_id - 1]["branch_role"] not in BRANCH_ROLE_VALUES:
            errors.append(f"Family {family_id}: invalid branch role {family_rows[family_id - 1]['branch_role']}")
        for role, person_id in (("father", father), ("mother", mother)):
            if person_id is not None and person_id not in people:
                errors.append(f"Family {family_id}: unknown {role} ID {person_id}")
        for child_id in children:
            if child_id not in people:
                errors.append(f"Family {family_id}: unknown child ID {child_id}")

    covered_families = set()
    for row in evidence_rows:
        evidence_id = row["evidence_id"]
        family_id = int(row["family_id"])
        covered_families.add(family_id)
        if not 1 <= family_id <= len(families):
            errors.append(f"{evidence_id}: unknown family ID {family_id}")
        if row["source_id"] not in sources:
            errors.append(f"{evidence_id}: unknown source ID {row['source_id']}")
        if row["relationship"] not in RELATIONSHIP_VALUES:
            errors.append(f"{evidence_id}: invalid relationship {row['relationship']}")
        if row["confidence"] not in CONFIDENCE_VALUES:
            errors.append(f"{evidence_id}: invalid confidence {row['confidence']}")
        for field in ("person_id", "related_person_id"):
            if row[field] and int(row[field]) not in people:
                errors.append(f"{evidence_id}: unknown {field} {row[field]}")
        if 1 <= family_id <= len(families):
            father, mother, children, _ = families[family_id - 1]
            person_id = int(row["person_id"]) if row["person_id"] else None
            related_id = int(row["related_person_id"]) if row["related_person_id"] else None
            if row["relationship"] == "spouse" and {person_id, related_id} != {father, mother}:
                errors.append(f"{evidence_id}: spouse IDs do not match family {family_id}")
            if row["relationship"] == "parent-child" and (
                person_id not in {father, mother} or related_id not in children
            ):
                errors.append(f"{evidence_id}: parent-child IDs do not match family {family_id}")

    for family_id in range(1, len(families) + 1):
        if family_id not in covered_families:
            errors.append(f"Family {family_id}: no relationship evidence")
    for source_id, source in sources.items():
        if not (DIRECTORY / source["file_name"]).is_file():
            errors.append(f"{source_id}: chart file not found: {source['file_name']}")

    if errors:
        raise SystemExit("\n".join(errors))
    print(
        f"Validated {len(people)} people, {len(families)} families, "
        f"{len(evidence_rows)} evidence records, and {len(sources)} source charts."
    )


if __name__ == "__main__":
    main()
