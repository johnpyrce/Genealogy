"""Export the reconciled Muszyna genealogy registries as GEDCOM 5.5.1."""

import csv
from pathlib import Path

from genealogy_data import load_families

DIRECTORY = Path(__file__).parent
REGISTRY = DIRECTORY / "genealogy_people_registry.csv"
OUTPUT = DIRECTORY / "merged_muszyna_family_tree.ged"

EXACT_DATES = {
    6: ("1 JAN 1816", None), 10: ("7 FEB 1852", "13 MAY 1902"),
    11: ("3 MAR 1853", "7 MAR 1926"), 14: ("27 MAY 1888", "11 MAY 1970"),
    15: ("25 FEB 1895", "9 OCT 1962"), 23: ("20 MAR 1920", "21 DEC 2001"),
    24: ("9 NOV 1927", "26 JAN 2004"), 28: ("21 APR 1922", "16 AUG 2010"),
    35: ("9 APR 1927", "2 JUL 2009"), 36: ("15 MAY 1932", "31 AUG 2020"),
    72: ("17 AUG 1930", "16 NOV 2015"), 73: ("5 MAR 1924", "22 JAN 2002"),
    152: ("8 JUL 1908", "11 JUL 2002"),
}


def line(level: int, tag: str, value: str = "") -> str:
    return f"{level} {tag}{' ' + value if value else ''}\n"


def date(year: str, person_id: int, event: str) -> str | None:
    exact = EXACT_DATES.get(person_id, (None, None))[0 if event == "BIRT" else 1]
    if exact:
        return exact
    if not year:
        return None
    return f"ABT {year}" if person_id == 1 else year


def main() -> None:
    with REGISTRY.open(encoding="utf-8", newline="") as source:
        people = list(csv.DictReader(source))
    families = load_families()
    family_ids: dict[int, list[str]] = {int(person["id"]): [] for person in people}
    child_family: dict[int, str] = {}
    for number, (partner_a, partner_b, children, _) in enumerate(families, start=1):
        family = f"@F{number}@"
        for partner in (partner_a, partner_b):
            if partner:
                family_ids[partner].append(family)
        for child in children:
            child_family.setdefault(child, family)

    output = [
        line(0, "HEAD"), line(1, "SOUR", "MUSZYNA-MERGE"),
        line(2, "NAME", "Merged Muszyna charts"), line(1, "GEDC"),
        line(2, "VERS", "5.5.1"), line(2, "FORM", "LINEAGE-LINKED"),
        line(1, "CHAR", "UTF-8"), line(1, "LANG", "English"),
        line(1, "NOTE", "Export derived from six user-supplied charts; see accompanying README for reconciliation limits."),
    ]
    for person in people:
        person_id = int(person["id"])
        output.append(line(0, f"@I{person_id}@ INDI"))
        display_name = person["first_name"] + (
            f" /{person['surname']}/" if person["surname"] != "Unknown" else ""
        )
        output.append(line(1, "NAME", display_name))
        output.append(line(1, "_SOURCE", person["source"]))
        birth = date(person["birth_year"], person_id, "BIRT")
        death = date(person["death_year"], person_id, "DEAT")
        if birth:
            output.extend([line(1, "BIRT"), line(2, "DATE", birth)])
        if death:
            output.extend([line(1, "DEAT"), line(2, "DATE", death)])
        if person["note"]:
            output.append(line(1, "NOTE", person["note"]))
        if person_id in child_family:
            output.append(line(1, "FAMC", child_family[person_id]))
        for family in family_ids[person_id]:
            output.append(line(1, "FAMS", family))

    for number, (partner_a, partner_b, children, note) in enumerate(families, start=1):
        output.append(line(0, f"@F{number}@ FAM"))
        if partner_a:
            output.append(line(1, "HUSB", f"@I{partner_a}@"))
        if partner_b:
            output.append(line(1, "WIFE", f"@I{partner_b}@"))
        for child in children:
            output.append(line(1, "CHIL", f"@I{child}@"))
        output.append(line(1, "NOTE", note))
    output.append(line(0, "TRLR"))
    OUTPUT.write_text("".join(output), encoding="utf-8")


if __name__ == "__main__":
    main()
