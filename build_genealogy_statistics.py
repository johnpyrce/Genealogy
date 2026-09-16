from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean, median, stdev

from genealogy_data import load_families, load_people

FAMILIES = load_families()

OUTPUT_DIR = Path(__file__).resolve().parent


# conservative inferences from the Polish given names; Pluto is left unknown.
MASCULINE_GIVEN_NAMES = {
    "Andrzej", "Antoni", "Bogdan", "Bogumił", "Bogusław", "Bolesław",
    "Bronisław", "Edward", "Emil", "Filip", "Franciszek", "Grzegorz",
    "Henryk", "Jakub", "Jan", "Józef", "Karol", "Konstanty", "Krzysztof",
    "Łukasz", "Maciej", "Marek", "Marcel", "Marcin", "Michał", "Mariusz",
    "Olivier", "Piotr", "Rafał", "Stanisław", "Tadeusz", "Wawrzyniec",
    "Wiesław", "Wincenty", "Wojciech",
}
FEMININE_GIVEN_NAMES = {
    "Agata", "Agnieszka", "Aleksandra", "Anna", "Antonina", "Barbara",
    "Bronisława", "Dorota", "Elżbieta", "Emilia", "Genowefa", "Grażyna",
    "Halina", "Hanna", "Helena", "Janina", "Joanna", "Józefa", "Karolina",
    "Katarzyna", "Magdalena", "Małgorzata", "Maria", "Marianna", "Maja",
    "Marta", "Martyna", "Michalina", "Natalia", "Paulina", "Renata", "Rita",
    "Stanisława", "Stefania", "Teresa", "Urszula", "Wanda", "Władysława", "Zofia",
}


def build_statistics():
    people = load_people()
    surname_counts = Counter(p["surname_group"] for p in people)
    first_counts = Counter(p["first"] for p in people)
    dated_births = [p for p in people if p["birth"] is not None]
    dated_deaths = [p for p in people if p["death"] is not None]
    earliest_birth = min(p["birth"] for p in dated_births)
    latest_birth = max(p["birth"] for p in dated_births)
    latest_event = max(p["death"] for p in dated_deaths)
    uncertain_count = sum(
        1
        for person in people
        if any(term in person["note"] for term in ("provisional", "uncertain", "illegible"))
    )
    unknown_surname_count = surname_counts["Unknown"]
    gender_counts = Counter(
        "Male" if p["first"] in MASCULINE_GIVEN_NAMES
        else "Female" if p["first"] in FEMININE_GIVEN_NAMES
        else "Unknown"
        for p in people
    )
    recorded_partners = {
        person_id
        for partner_a, partner_b, _, _ in FAMILIES
        if partner_a and partner_b
        for person_id in (partner_a, partner_b)
    }
    family_sizes = [len(children) for _, _, children, _ in FAMILIES]
    child_recorded_sizes = [size for size in family_sizes if size]
    lifespans = [p["death"] - p["birth"] for p in people if p["birth"] is not None and p["death"] is not None]
    lifespan_bands = Counter((age // 10) * 10 for age in lifespans)
    people_by_id = {p["id"]: p for p in people}
    parent_ages = {"father": [], "mother": []}
    parent_child_pairs = {"father": 0, "mother": 0}
    for father, mother, children, _ in FAMILIES:
        for role, parent_id in (("father", father), ("mother", mother)):
            if parent_id is None:
                continue
            for child_id in children:
                parent_child_pairs[role] += 1
                parent = people_by_id[parent_id]
                child = people_by_id[child_id]
                if parent["birth"] is not None and child["birth"] is not None:
                    parent_ages[role].append(child["birth"] - parent["birth"])
    parent_age_bands = {
        "Under 20": lambda age: age < 20,
        "20–24": lambda age: 20 <= age <= 24,
        "25–29": lambda age: 25 <= age <= 29,
        "30–34": lambda age: 30 <= age <= 34,
        "35–39": lambda age: 35 <= age <= 39,
        "40 and over": lambda age: age >= 40,
    }
    all_parent_ages = parent_ages["father"] + parent_ages["mother"]
    parent_age_distribution = [
        [band, sum(matches(age) for age in all_parent_ages)]
        for band, matches in parent_age_bands.items()
    ]

    # Generational width for the main connected descendant network, excluding spouses.
    # Generation 1 begins with Wawrzyniec Gościński (about 1760).
    confirmed_generation_counts = [1, 1, 2, 1, 5, 13, 12, 12, 9]
    inclusive_generation_counts = [1, 3, 2, 1, 6, 13, 14, 16, 15, 1]

    summary = {
        "people": len(people),
        "known_surnames": len(people) - unknown_surname_count,
        "unknown_surnames": unknown_surname_count,
        "confirmed_depth": len(confirmed_generation_counts),
        "inclusive_depth": len(inclusive_generation_counts),
        "confirmed_width": max(confirmed_generation_counts),
        "inclusive_width": max(inclusive_generation_counts),
        "birth_range": f"about {earliest_birth}–{latest_birth}",
        "event_range": f"about {earliest_birth}–{latest_event}",
        "uncertain_people": uncertain_count,
        "male": gender_counts["Male"],
        "female": gender_counts["Female"],
        "gender_unknown": gender_counts["Unknown"],
        "recorded_partner": len(recorded_partners),
        "no_recorded_partner": len(people) - len(recorded_partners),
        "family_records": len(FAMILIES),
        "child_recorded_families": len(child_recorded_sizes),
        "child_links": sum(family_sizes),
        "family_size_mean": mean(child_recorded_sizes),
        "family_size_median": median(child_recorded_sizes),
        "family_size_sd": stdev(child_recorded_sizes),
        "family_size_max": max(child_recorded_sizes),
        "lifespan_count": len(lifespans),
        "lifespan_mean": mean(lifespans),
        "lifespan_median": median(lifespans),
        "lifespan_sd": stdev(lifespans),
        "lifespan_min": min(lifespans),
        "lifespan_max": max(lifespans),
        "father_age_count": len(parent_ages["father"]),
        "father_age_mean": mean(parent_ages["father"]),
        "father_age_median": median(parent_ages["father"]),
        "father_age_min": min(parent_ages["father"]),
        "father_age_max": max(parent_ages["father"]),
        "father_age_coverage": parent_child_pairs["father"],
        "mother_age_count": len(parent_ages["mother"]),
        "mother_age_mean": mean(parent_ages["mother"]),
        "mother_age_median": median(parent_ages["mother"]),
        "mother_age_min": min(parent_ages["mother"]),
        "mother_age_max": max(parent_ages["mother"]),
        "mother_age_coverage": parent_child_pairs["mother"],
        "parent_age_count": len(all_parent_ages),
        "parent_age_mean": mean(all_parent_ages),
        "parent_age_median": median(all_parent_ages),
        "parent_age_min": min(all_parent_ages),
        "parent_age_max": max(all_parent_ages),
    }

    surname_rows = sorted(surname_counts.items(), key=lambda item: (-item[1], item[0]))
    first_rows = sorted(first_counts.items(), key=lambda item: (-item[1], item[0]))
    top_first_rows = first_rows[:10]
    oldest = sorted(dated_births, key=lambda p: (p["birth"], p["first"], p["surname"]))[:10]
    oldest_rows = []
    for person in oldest:
        full_name = f"{person['first']} {person['surname']}".strip()
        birth = f"about {person['birth']}" if person["birth"] == 1760 else str(person["birth"])
        lifespan = birth
        if person["death"]:
            lifespan += f"–{person['death']}"
        oldest_rows.append([full_name, lifespan, person["note"] or "—"])

    markdown = [
        "# Statistics for the Combined Muszyna Family Tree",
        "",
        f"- **Distinct people:** {len(people)}",
        f"- **Known surnames:** {len(people) - unknown_surname_count}",
        f"- **Surname unavailable or unclear:** {unknown_surname_count}",
        "- **Supported tree depth:** 9 generations (8 parent-child steps)",
        "- **Inclusive depth:** 10 generations (9 steps), using provisional handwritten links",
        f"- **Supported maximum width:** {summary['confirmed_width']} people in one generation",
        f"- **Inclusive maximum width:** {summary['inclusive_width']} people in one generation",
        f"- **Birth-year range:** about {earliest_birth}–{latest_birth}",
        f"- **All-event range:** about {earliest_birth}–{latest_event}",
        "",
        "## Gender, recorded partnership, and family size",
        "",
        "| Measure | Count / value |",
        "| --- | ---: |",
        f"| Inferred female | {summary['female']} |",
        f"| Inferred male | {summary['male']} |",
        f"| Gender not inferred | {summary['gender_unknown']} |",
        f"| People with a recorded spouse or partner | {summary['recorded_partner']} |",
        f"| No spouse or partner recorded | {summary['no_recorded_partner']} |",
        f"| Family or household records | {summary['family_records']} |",
        f"| Families with one or more children recorded | {summary['child_recorded_families']} |",
        f"| Documented child links | {summary['child_links']} |",
        f"| Mean children per family with children recorded | {summary['family_size_mean']:.2f} |",
        f"| Median children per family with children recorded | {summary['family_size_median']:.0f} |",
        f"| Sample standard deviation of family size | {summary['family_size_sd']:.2f} |",
        f"| Largest recorded family size | {summary['family_size_max']} |",
        "",
        "A recorded partner is not proof of marriage, and no recorded partner is not proof that a person was single. The charts often omit partners, marriages, and children. Gender is inferred from the written Polish given name; one entry (Pluto) remains unknown.",
        "",
        "## Lifespan statistics",
        "",
        "Lifespan is the difference between the recorded birth and death years, so it is an approximate whole-year measure. Only people with both years are included.",
        "",
        "| Measure | Years |",
        "| --- | ---: |",
        f"| People with a calculable lifespan | {summary['lifespan_count']} |",
        f"| Average lifespan (arithmetic mean) | {summary['lifespan_mean']:.1f} |",
        f"| Mean lifespan | {summary['lifespan_mean']:.1f} |",
        f"| Median lifespan | {summary['lifespan_median']:.1f} |",
        f"| Sample standard deviation | {summary['lifespan_sd']:.1f} |",
        f"| Observed range | {summary['lifespan_min']}–{summary['lifespan_max']} |",
        "",
        "### Lifespan distribution",
        "",
        "| Age at death | People | Distribution |",
        "| --- | ---: | --- |",
    ]
    for band in range(40, 100, 10):
        count = lifespan_bands[band]
        markdown.append(f"| {band}–{band + 9} | {count} | {'█' * count} |")
    markdown.extend(
        [
            "",
            "## Parent age when children were born",
            "",
            "Parent age is the child’s recorded birth year minus the recorded birth year of the parent. It is an approximate whole-year measure and includes only links with both years recorded. Father and mother describe the recorded family-registry role.",
            "",
            "| Parent role | Observations | Mean | Median | Observed range | Year coverage |",
            "| --- | ---: | ---: | ---: | --- | --- |",
            f"| Father | {summary['father_age_count']} | {summary['father_age_mean']:.1f} | {summary['father_age_median']:.0f} | {summary['father_age_min']}–{summary['father_age_max']} | {summary['father_age_count']} of {summary['father_age_coverage']} links |",
            f"| Mother | {summary['mother_age_count']} | {summary['mother_age_mean']:.1f} | {summary['mother_age_median']:.0f} | {summary['mother_age_min']}–{summary['mother_age_max']} | {summary['mother_age_count']} of {summary['mother_age_coverage']} links |",
            f"| Combined | {summary['parent_age_count']} | {summary['parent_age_mean']:.1f} | {summary['parent_age_median']:.0f} | {summary['parent_age_min']}–{summary['parent_age_max']} | Recorded birth years only |",
            "",
            "### Distribution",
            "",
            "| Parent age | Parent-child observations |",
            "| --- | ---: |",
        ]
    )
    markdown.extend(f"| {band} | {count} |" for band, count in parent_age_distribution)
    markdown.extend(["", "## Count by family name", "", "| Family name group | People |", "| --- | ---: |"])
    markdown.extend(f"| {name} | {count} |" for name, count in surname_rows)
    markdown.extend(["", "## Most common first names", "", "| First name | People |", "| --- | ---: |"]) 
    markdown.extend(f"| {name} | {count} |" for name, count in top_first_rows)
    markdown.extend(["", "## Oldest people with recorded birth years", "", "| Person | Recorded years |", "| --- | --- |"])
    markdown.extend(f"| {row[0]} | {row[1]} |" for row in oldest_rows)
    markdown.extend(
        [
            "",
            "## Method",
            "",
            "Counts reconcile duplicate appearances across the six charts. Spouses and side-pedigree people are included. Surname groups combine masculine and feminine Polish forms. People lacking a readable surname remain in the total and first-name counts. Depth and width exclude spouses and are reported both with and without explicitly provisional relationships. Gender, relationship, family-size, and lifespan measures are chart-derived summaries rather than complete civil-record measures; their scope and qualifications are stated above.",
            "",
        ]
    )
    (OUTPUT_DIR / "genealogy_statistics.md").write_text("\n".join(markdown), encoding="utf-8")

    csv_lines = ["id,first_name,surname,family_name_group,birth_year,death_year,source,note"]
    import csv
    import io

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(csv_lines[0].split(","))
    for p in people:
        writer.writerow([p["id"], p["first"], p["surname"], p["surname_group"], p["birth"] or "", p["death"] or "", p["source"], p["note"]])
    (OUTPUT_DIR / "genealogy_people_registry.csv").write_text(stream.getvalue(), encoding="utf-8")

    print(summary)
    print("Top surnames:", surname_rows[:10])
    print("Top first names:", first_rows[:10])
    print("Oldest:", [(p["first"], p["surname"], p["birth"]) for p in oldest])


if __name__ == "__main__":
    build_statistics()
