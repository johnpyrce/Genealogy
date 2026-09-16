"""Shared loaders for the editable genealogy registries."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRIES = ROOT / "data" / "registries"
PEOPLE_REGISTRY = REGISTRIES / "people.csv"
FAMILY_REGISTRY = REGISTRIES / "families.csv"
SOURCE_REGISTRY = REGISTRIES / "sources.csv"
EVIDENCE_REGISTRY = REGISTRIES / "relationship_evidence.csv"
PERSON_SOURCE_REGISTRY = REGISTRIES / "person_source_evidence.csv"


def load_people() -> list[dict[str, str | int | None]]:
    """Return normalized person records from the people CSV registry."""
    people = []
    with PEOPLE_REGISTRY.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            people.append(
                {
                    "id": int(row["id"]),
                    "first": row["first_name"],
                    "surname": row["surname"],
                    "surname_group": row["family_name_group"] or "Unknown",
                    "birth": int(row["birth_year"]) if row["birth_year"] else None,
                    "death": int(row["death_year"]) if row["death_year"] else None,
                    "source": row["source"],
                    "note": row["note"],
                }
            )
    return people


def load_families() -> list[tuple[int | None, int | None, list[int], str]]:
    """Return (father, mother, children, note) tuples from the family CSV."""
    families = []
    with FAMILY_REGISTRY.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            father = int(row["father_id"]) if row["father_id"] else None
            mother = int(row["mother_id"]) if row["mother_id"] else None
            children = [int(value) for value in row["children_ids"].split(";") if value]
            families.append((father, mother, children, row["note"]))
    return families


def load_sources() -> dict[str, dict[str, str]]:
    with SOURCE_REGISTRY.open(encoding="utf-8", newline="") as source:
        return {row["source_id"]: row for row in csv.DictReader(source)}


def load_relationship_evidence() -> list[dict[str, str]]:
    with EVIDENCE_REGISTRY.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def load_person_source_evidence() -> list[dict[str, str]]:
    with PERSON_SOURCE_REGISTRY.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def person_source_ids() -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for evidence in load_person_source_evidence():
        person_id = int(evidence["person_id"])
        source_id = evidence["source_id"]
        if source_id not in result.setdefault(person_id, []):
            result[person_id].append(source_id)
    return result


def family_source_ids() -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for evidence in load_relationship_evidence():
        family_id = int(evidence["family_id"])
        source_id = evidence["source_id"]
        if source_id not in result.setdefault(family_id, []):
            result[family_id].append(source_id)
    return result


def family_branch_roles() -> dict[int, str]:
    with FAMILY_REGISTRY.open(encoding="utf-8", newline="") as source:
        return {int(row["id"]): row["branch_role"] for row in csv.DictReader(source)}
