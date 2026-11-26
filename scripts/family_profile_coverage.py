"""Summarize recorded fields without reducing GEDCOM facts to profile years."""
from __future__ import annotations

from collections import defaultdict
import re

from scripts.import_gedcom import Node, incoming_person
from scripts.lib.genealogy_data import load_person_source_evidence, load_relationship_evidence

PERSON_EVENTS = {
    "BIRT": "Birth", "DEAT": "Death", "BURI": "Burial", "CHR": "Christening",
    "BAPM": "Baptism", "CREM": "Cremation", "ADOP": "Adoption", "BARM": "Bar mitzvah",
    "BASM": "Bat mitzvah", "BLES": "Blessing", "CHRA": "Adult christening",
    "CONF": "Confirmation", "FCOM": "First communion", "ORDN": "Ordination",
    "RESI": "Residence", "CENS": "Census", "IMMI": "Immigration", "EMIG": "Emigration",
    "NATU": "Naturalization", "OCCU": "Occupation", "EDUC": "Education",
    "GRAD": "Graduation", "RETI": "Retirement", "PROB": "Probate", "WILL": "Will",
    "EVEN": "Other life event", "FACT": "Other personal fact",
}
FAMILY_EVENTS = {
    "MARR": "Marriage", "DIV": "Divorce", "ENGA": "Engagement",
    "MARB": "Marriage banns", "MARC": "Marriage contract", "MARL": "Marriage license",
    "MARS": "Marriage settlement", "ANUL": "Annulment", "DIVF": "Divorce filing",
    "CENS": "Family census", "RESI": "Family residence", "FACT": "Other family fact",
    "EVEN": "Other family event",
}
CORE_EVENTS = {"BIRT", "DEAT", "BURI", "CHR", "MARR", "DIV"}
MONTH = "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC"
YEAR = re.compile(rf"(?:(?:[0-9]{{1,2}} )?(?:{MONTH}) )?([0-9]{{1,4}})")


def recorded_years(date: str) -> list[int]:
    """Read written Gregorian year endpoints without estimating missing bounds."""
    date = " ".join(date.upper().split())
    chunks = re.split(r" (?:AND|TO) ", date)
    years = []
    for chunk in chunks:
        chunk = re.sub(r"^(?:ABT|CAL|EST|BEF|AFT|BET|FROM|TO) ", "", chunk)
        chunk = re.sub(r"^(?:@#DGREGORIAN@|GREGORIAN) ", "", chunk)
        match = YEAR.fullmatch(chunk)
        if match is None:
            return []
        years.append(int(match[1]))
    return years


def person_name(person: dict) -> str:
    return " ".join(filter(None, (person["first"], person["surname"]))) or "Name unknown"


def count_parents(families: list[tuple]) -> dict[int, set[int]]:
    parents = defaultdict(set)
    for father, mother, children, _ in families:
        for child in children:
            parents[child].update(parent for parent in (father, mother) if parent is not None)
    return parents


def section(title: str, records: list[dict]) -> dict:
    return {"title": title, "records": records, "rows": []}


def metric(group: dict, label: str, values: dict | None, eligible: list[int] | None = None) -> None:
    row = {"label": label, "values": values}
    if eligible is not None:
        row["eligible"] = eligible
    group["rows"].append(row)


def field(records: list[dict], key: str) -> dict[int, str]:
    return {i: record[key] for i, record in enumerate(records) if record.get(key)}


def record_labels(people: list[dict], families: list[tuple], references: list[str]) -> tuple[list, list]:
    names = {person["id"]: person_name(person) for person in people}
    individuals = [
        {"name": names[p["id"]], "reference": p.get("reference", f"Person {p['id']}")}
        for p in people
    ]
    households = [
        {"name": " / ".join(names[x] for x in (father, mother) if x is not None) or "Family with no named partners",
         "reference": references[i] if references else f"Family {i + 1}"}
        for i, (father, mother, _, _) in enumerate(families)
    ]
    return individuals, households


def registry_coverage(people: list[dict], families: list[tuple]) -> tuple[dict, list[int]]:
    individuals, households = record_labels(people, families, [])
    parents = count_parents(families)
    people_group = section("People", individuals)
    for label, key in (("Given name", "first"), ("Surname", "surname"), ("Birth year", "birth"),
                       ("Death year", "death"), ("Notes", "note")):
        metric(people_group, label, field(people, key))
    metric(people_group, "At least one linked parent", {
        i: str(len(parents[p["id"]])) for i, p in enumerate(people) if parents[p["id"]]
    })
    family_group = section("Families", households)
    metric(family_group, "Two linked partners", {
        i: "Two partners" for i, (father, mother, _, _) in enumerate(families)
        if father is not None and mother is not None
    })
    metric(family_group, "Marriage date", None)
    places = section("Places", [])
    for label in ("Birthplace", "Death place", "Burial place", "Marriage place"):
        metric(places, label, None)
    person_evidence = defaultdict(set)
    family_evidence = defaultdict(set)
    for row in load_person_source_evidence():
        person_evidence[int(row["person_id"])].add(row["source_id"])
    for row in load_relationship_evidence():
        family_evidence[int(row["family_id"])].add(row["source_id"])
    evidence = section("Evidence · People", individuals)
    metric(evidence, "Source evidence", {
        i: ", ".join(sorted(person_evidence[p["id"]]))
        for i, p in enumerate(people) if person_evidence[p["id"]]
    })
    family_sources = section("Evidence · Families", households)
    metric(family_sources, "Relationship evidence", {
        i: ", ".join(sorted(family_evidence[i + 1])) for i in range(len(families))
        if family_evidence[i + 1]
    })
    years = [p[key] for p in people for key in ("birth", "death") if p[key] is not None]
    return {"label": "Project registry", "groups": [people_group, family_group, places, evidence, family_sources]}, years


def entries(node: Node, *tags: str) -> str:
    return ", ".join(dict.fromkeys(child.value.strip() or child.get("PHRASE").strip()
                                  for child in node.children if child.tag in tags
                                  and (child.value.strip() or child.get("PHRASE").strip())))


def documented(node: Node, *tags: str) -> bool:
    return any(child.tag in tags and (child.value.strip() or child.children) for child in node.children)


def inventory(owners: list[Node], excluded: set[str]) -> dict:
    found = defaultdict(set)
    for i, owner in enumerate(owners):
        for child in owner.children:
            if child.tag not in excluded:
                found[child.tag].add(i)
    return found


def add_evidence(group: dict, records: list[Node]) -> None:
    for label, tags in (("Source citations", ("SOUR",)), ("Notes", ("NOTE", "SNOTE")),
                        ("Media links", ("OBJE",))):
        metric(group, label, {i: "Recorded" for i, record in enumerate(records)
                              if documented(record, *tags)})


def gedcom_coverage(label: str, records: list[Node]) -> tuple[dict, list[int]]:
    people = [record for record in records if record.tag == "INDI"]
    families = [record for record in records if record.tag == "FAM"]
    names = {}
    for person in people:
        facts = incoming_person(person)
        names[person.xref] = person_name({"first": facts["first_name"], "surname": facts["surname"]})
    people_labels = [{"name": names[p.xref], "reference": p.xref} for p in people]
    family_labels = [{
        "name": " / ".join(names[record.get(tag)] for tag in ("HUSB", "WIFE") if record.get(tag))
        or "Family with no named partners", "reference": record.xref,
    } for record in families]
    groups = []
    evidence_groups = []
    extra_groups = []
    event_nodes = []
    events = []
    event_indices = {}
    years = []
    linked_children = {child.value for family in families if family.get("HUSB") or family.get("WIFE")
                       for child in family.all("CHIL")}
    for scope, owners, labels, event_types in (
        ("People", people, people_labels, PERSON_EVENTS),
        ("Families", families, family_labels, FAMILY_EVENTS),
    ):
        group = section(scope, labels)
        if scope == "People":
            metric(group, "Name", {i: names[p.xref] for i, p in enumerate(people)
                                   if names[p.xref] != "Name unknown"})
            metric(group, "Alternate names", {i: entries(p, "NAME") or "Recorded"
                                              for i, p in enumerate(people)
                                              if sum(bool(n.value.strip() or n.get("GIVN") or n.get("SURN"))
                                                     for n in p.all("NAME")) > 1})
            metric(group, "Sex recorded", {i: p.get("SEX") for i, p in enumerate(people)
                                           if p.get("SEX").strip().upper() not in {"", "U"}})
            metric(group, "At least one linked parent", {
                i: "Recorded" for i, p in enumerate(people) if p.xref in linked_children
            })
        else:
            metric(group, "Two linked partners", {i: "Two partners" for i, f in enumerate(families)
                                                  if f.get("HUSB") and f.get("WIFE")})
        groups.append(group)
        extra = section(f"Other fields in this export · {scope.lower()}", labels)
        extra_fields = inventory(owners, set(event_types) | {
            "NAME", "SEX", "FAMC", "FAMS", "HUSB", "WIFE", "CHIL", "SOUR", "NOTE", "SNOTE",
            "OBJE", "CHAN", "CREA", "UID", "_UID", "_FSFTID",
        })
        # Extensions with dates or places use the same detail rows as standard events.
        extra_events = {entry.tag for owner in owners for entry in owner.children
                        if entry.tag in extra_fields and (entry.all("DATE") or entry.all("PLAC"))}
        for tag, event_type in {**event_types, **{tag: tag for tag in sorted(extra_events)}}.items():
            values = defaultdict(list)
            dates_by_owner = defaultdict(list)
            places_by_owner = defaultdict(list)
            indices = []
            for i, owner in enumerate(owners):
                for event in owner.all(tag):
                    date = entries(event, "DATE")
                    locations = list(dict.fromkeys(location.value.strip() for location in event.all("PLAC")
                                                   if location.value.strip()))
                    place = "; ".join(locations)
                    detail = " · ".join(filter(None, (event.get("TYPE").strip(), date, place)))
                    values[i].append(detail or "Entry recorded")
                    if date:
                        dates_by_owner[i].append(date)
                    if place:
                        places_by_owner[i].append(place)
                    coordinates = [f"{mapping.get('LATI')}, {mapping.get('LONG')}"
                                   for location in event.all("PLAC") for mapping in location.all("MAP")
                                   if mapping.get("LATI") and mapping.get("LONG")]
                    indices.append(len(events))
                    event_nodes.append(event)
                    events.append({**labels[i], "event": event_type, "date": date, "locations": locations,
                                   "place": place, "coordinates": "; ".join(coordinates)})
                    for date_node in event.all("DATE"):
                        years.extend(recorded_years(date_node.value))
            if tag in CORE_EVENTS or values:
                event_indices[scope, event_type] = indices
                metric(group if tag in CORE_EVENTS else extra, f"{event_type} entries",
                       {i: "; ".join(parts) for i, parts in values.items()})
            if tag in {"BIRT", "DEAT"}:
                metric(group, f"{event_type} date",
                       {i: "; ".join(dict.fromkeys(parts)) for i, parts in dates_by_owner.items()})
                metric(group, "Birthplace" if tag == "BIRT" else "Death place",
                       {i: "; ".join(dict.fromkeys(parts)) for i, parts in places_by_owner.items()})
        add_evidence(evidence := section(f"Evidence · {scope}", labels), owners)
        evidence_groups.append(evidence)
        for tag in sorted(extra_fields.keys() - extra_events):
            metric(extra, tag, dict.fromkeys(sorted(extra_fields[tag]), "Entry recorded"))
        if extra["rows"]:
            extra_groups.append(extra)
    dates = section("Event dates", events)
    places = section("Places", events)
    for (_, event_type), eligible in event_indices.items():
        metric(dates, f"{event_type} date", {
            i: events[i]["date"] for i in eligible if events[i]["date"]
        }, eligible)
        metric(places, f"{event_type} place", {
            i: events[i]["place"] for i in eligible if events[i]["place"]
        }, eligible)
    with_places = [i for i, event in enumerate(events) if event["place"]]
    metric(places, "Coordinates", {i: events[i]["coordinates"] for i in with_places
                                  if events[i]["coordinates"]}, with_places)
    event_evidence = section("Evidence · Event entries", events)
    add_evidence(event_evidence, event_nodes)
    return {"label": label, "events": events,
            "groups": [*groups, dates, places, *evidence_groups, event_evidence, *extra_groups]}, years


def build_coverage(people: list[dict], families: list[tuple],
                   sources: list[tuple[str, list[Node]]] | None) -> dict:
    if sources:
        reports = [gedcom_coverage(label, records) for label, records in sources]
    else:
        reports = [registry_coverage(people, families)]
    years = [year for _, found in reports for year in found]
    parents = count_parents(families)
    return {"without_parents": sum(not parents[p["id"]] for p in people),
            "years": [min(years), max(years)] if years else None,
            "sources": [report for report, _ in reports]}
