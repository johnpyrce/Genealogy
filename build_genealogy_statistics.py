from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean, median, stdev

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from genealogy_data import load_families

FAMILIES = load_families()

OUTPUT_DIR = Path(__file__).resolve().parent


# One row per person after reconciling repeated appearances across the charts.
# Empty surnames mean that only a first name was legible or supplied.
RAW_PEOPLE = """
Wawrzyniec|Gościński|1760||printed|approximate birth year
Teresa|Bartmanowicz|||printed|
Wawrzyniec|Gościński|1780||printed|
Stanisław|Gościński|1785||printed|relationship provisional
Jakub|Gościński|1788||printed|relationship provisional
Antoni|Gościński|1816||printed|
Katarzyna|Grotkowska|||printed|
Maria|Sasała|||printed|
Maria|Tryszczyła|||printed|
Franciszek|Gościński|1852|1902|printed|
Józefa|Szost|1853|1926|printed|
Maria|Gościńska|||printed|
Antoni|Drozd|1815||printed|
Jan|Gościński|1888|1970|both|
Marianna|Miczulska|1895|1962|both|
Józef|Gościński|1895||printed|
Joanna|Gościńska|||printed|
Andrzej|Gościński|||both|
Franciszek|Gościński|||printed-only sibling|
Magdalena|Gościńska|||printed-only sibling|
Piotr|Szost|1861||printed|
Zofia|Gościńska|||handwritten-only sibling|
Bronisław|Gościński|1920|2001|both|
Władysława|Śliwa|1927|2004|both|
Teresa||||handwritten|
Marta||||handwritten|
Barbara||||handwritten|
Edward|Gościński|1922|2010|both|
Anna|Maślanka|1928||both|
Marek||||handwritten|
Stanisław|Gościński|1923||both|
Jan|Gościński|1925|1985|both|
Zofia|Jacenik|||both|
Mariusz||||handwritten|
Stanisław|Gościński|1927|2009|both|
Władysława|Miczulska|1932|2020|both|
Antonina||||handwritten|child in recent branch
Joanna||||handwritten|relationship provisional
Józef|Berduchowski|||handwritten|surname provisional
Jakub||||handwritten|
Emilia|Pawlowska|||handwritten|relationship provisional
Krzysztof||||handwritten|
Łukasz||||handwritten|
Katarzyna|Sułkowska|||handwritten|surname provisional
Emilia||||handwritten|
Olivier||||handwritten|
Marta||||handwritten|
Marcin||||handwritten|surname illegible
Maja||||handwritten|
Marcel||||handwritten|
Grażyna||||handwritten|
Andrzej|Drabyk|||handwritten|surname provisional
Elżbieta||||handwritten|marked deceased
Wanda|Gościńska|||both|
Bogumił|Gościński|||polished|
Magdalena|Gościńska|||polished|
Łukasz|Wiśniewski|||polished|
Filip|Wiśniewski|||polished|
Martyna|Wiśniewska|||polished|
Rafał|Gościński|||polished|
Joanna|Kowalczyk|||polished|
Aleksandra|Gościńska|||polished|
Dorota|Gościńska|||polished|
Paulina|Gościńska|||polished|
Grzegorz|Hryc|||polished|
Konstanty|Hryc|||polished|
Wincenty|Hryc|||polished|
Renata|Gościńska|||polished|
Małgorzata||||handwritten|
Bogdan||||handwritten|generation uncertain
Pluto||||handwritten|name and generation uncertain
Bronisława|Gościńska|1930|2015|both|
Bolesław|Rams|1924|2002|both|
Antonina|Gościńska|1936||printed|
Bronisław|Miąsik|||printed|
Jan|Pyrc|||handwritten|
Anna|Bukowska|||handwritten|
Józef|Pyrc|||handwritten|
Emil|Pyrc|||handwritten|
Stanisław|Pyrc|||handwritten|
Tadeusz|Pyrc|||both|
Karol|Pyrc|||both|
Bronisława|Pyrc|||both|
Stefania|Pyrc|||both|
Maria|Pyrc|||handwritten|
Jan|Storoż|||handwritten|surname provisional
Franciszek|Pyrc|||handwritten|
Marcin|Rams|||printed|
Anna|Tryszczyła|||printed|
Wawrzyniec|Rams|||printed|relationship provisional
Agata||||printed|
Wojciech|Rams|1880|1953|printed|
Stanisław|Rams|1894|1957|printed|
Joanna|Gruczelak|1901|1994|printed|
Małgorzata|Rams|1958||printed|
Henryk|Drzązgowski|1957|2002|printed|
Józef|Drost|1961||printed|relationship placement uncertain
Joanna|Drzązgowska|1985||printed|
Aleksandra|Drzązgowska|1987||printed|
Michał|Drzązgowski|1988||printed|
Bogusław|Rams|1960||printed|
Halina|Dulak|1965||printed|
Maciej|Rams|1990||printed|
Natalia|Tokarczyk|1993||printed|
Hanna|Rams|2021||printed|relationship provisional
Wojciech|Rams|1995||printed|
Natalia|Drobny|||printed|
Urszula|Rams|2000||printed|
Wojciech|Walczyk|||printed|
Marta|Rams|1965||printed|
Wiesław|Kokoszka|1959||printed|
Karolina|Kokoszka|1987||printed|
Anna|Kokoszka|1988||printed|
Jan|Romer|||printed|
Rita|Romer|2023||printed|relationship provisional
Marta|Romer|||printed|relationship provisional
Jan|Rams|1908|1988|printed|
Helena|Ruchałowska|1909|2005|printed|
Józef|Rams|||printed|
Zofia|Ślaby|1914|2004|printed|
Michalina|Rams|1917|1996|printed|
Józef|Tokarczyk|1909|1984|printed|
Michał|Rams|1910|1974|printed|
Katarzyna||||printed|wife placement uncertain
Janina|Fedorczak|||printed|
Stanisława|Rams|1923|2013|printed|
Józef|Cisowski|1913|1995|printed|
Henryk|Rams|1927|2024|printed|
Genowefa|Gumuliak|1932|2015|printed|
Wawrzyniec|Miczulski|||printed|
Małgorzata|Kałucka|||printed|surname provisional
Piotr|Miczulski|1805||printed|
Marianna|Sajdak|||printed|
Katarzyna|Fedorczak|||printed|connector provisional
Jan|Miczulski|1833||printed|
Katarzyna|Łyga|||printed|connector provisional
Jan|Moszczak|1860|1952|printed|
Maria|Wilczyńska|1861|1953|printed|
Michał|Homa|1839||printed|
Marianna|Krajowska|||printed|
Agnieszka|Homa|1884|1968|printed|
Franciszek|Miczulski|1899|1965|printed|
Stanisław|Śliwa|1871|1950|printed|
Zofia|Homa|1886|1927|printed|
Franciszek|Śliwa|1905|1981|printed|
Maria|Moszczak|1903|1993|printed|
Józef|Szost|1803||printed|
Maria|Matusiewicz|||printed|
Franciszek|Szost|1832||printed|
Zofia|Wilczyńska|||printed|
Jan|Gruczelak|1854||printed|
Piotr|Jacenik|1908|2002|printed|corrected from the S2 spouse pedigree
Antonina|Bukowska|||printed|
Maria|Gruczelak|||printed|previous extraction; relationship not verified in S2
Zofia|Matusiewicz|||printed|spouse of Wawrzyniec Gościński (1780)
Unknown|Łyga|||printed|first name not shown in S2
"""


SURNAME_GROUPS = {
    "Gościńska": "Gościński",
    "Miczulska": "Miczulski",
    "Wiśniewska": "Wiśniewski",
    "Drzązgowska": "Drzązgowski",
    "Pawlowska": "Pawlowski",
    "Sułkowska": "Sułkowski",
    "Ruchałowska": "Ruchałowski",
    "Kałucka": "Kałucki",
    "Krajowska": "Krajowski",
    "Wilczyńska": "Wilczyński",
    "Bukowska": "Bukowski",
    "Grotkowska": "Grotkowski",
}


# The source charts do not carry an explicit sex/gender field. These sets are
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


def load_people():
    people = []
    for index, line in enumerate(RAW_PEOPLE.strip().splitlines(), start=1):
        first, surname, birth, death, source, note = line.split("|")
        people.append(
            {
                "id": index,
                "first": first,
                "surname": surname,
                "surname_group": SURNAME_GROUPS.get(surname, surname) if surname else "Unknown",
                "birth": int(birth) if birth else None,
                "death": int(death) if death else None,
                "source": source,
                "note": note,
            }
        )
    return people


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def remove_paragraph_border(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    border = p_pr.find(qn("w:pBdr"))
    if border is not None:
        p_pr.remove(border)
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "nil")
    border.append(bottom)
    p_pr.append(border)


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for i, label in enumerate(headers):
        cell = hdr.cells[i]
        cell.text = str(label)
        set_cell_shading(cell, "1F4E78")
        set_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        for run in cell.paragraphs[0].runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9.5)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r_idx, row_data in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row_data):
            cells[i].text = str(value)
            cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cells[i])
            if r_idx % 2:
                set_cell_shading(cells[i], "F2F6FA")
            for run in cells[i].paragraphs[0].runs:
                run.font.size = Pt(9.5)
            cells[i].paragraphs[0].alignment = (
                WD_ALIGN_PARAGRAPH.LEFT if i == 0 else WD_ALIGN_PARAGRAPH.CENTER
            )
    if widths:
        for row in table.rows:
            for i, width in enumerate(widths):
                row.cells[i].width = Inches(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_metric_table(doc, metrics):
    table = doc.add_table(rows=2, cols=len(metrics))
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    table.autofit = False
    for i, (label, value) in enumerate(metrics):
        top = table.cell(0, i)
        bottom = table.cell(1, i)
        top.text = value
        bottom.text = label
        for cell in (top, bottom):
            set_cell_shading(cell, "EAF2F8")
            set_cell_margins(cell, top=130, bottom=130)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in top.paragraphs[0].runs:
            run.font.size = Pt(19)
            run.font.bold = True
            run.font.color.rgb = RGBColor(31, 78, 120)
        for run in bottom.paragraphs[0].runs:
            run.font.size = Pt(9)
            run.font.bold = True
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(item)


def build_document():
    people = load_people()
    surname_counts = Counter(p["surname_group"] for p in people)
    first_counts = Counter(p["first"] for p in people)
    dated_births = [p for p in people if p["birth"] is not None]
    dated_deaths = [p for p in people if p["death"] is not None]
    earliest_birth = min(p["birth"] for p in dated_births)
    latest_birth = max(p["birth"] for p in dated_births)
    latest_event = max(p["death"] for p in dated_deaths)
    uncertain_count = sum(
        1 for p in people if "provisional" in p["note"] or "uncertain" in p["note"] or "illegible" in p["note"]
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

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)

    styles = doc.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(10.5)
    styles["Normal"].paragraph_format.space_after = Pt(6)
    for style_name, size in (("Title", 24), ("Heading 1", 16), ("Heading 2", 12)):
        style = styles[style_name]
        style.font.name = "Aptos Display" if style_name != "Normal" else "Aptos"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(10)
        style.paragraph_format.space_after = Pt(5)

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    title.add_run("Statistics for the Combined Muszyna Family Tree")
    remove_paragraph_border(title)
    intro = doc.add_paragraph()
    intro.add_run(
        f"The reconciled charts contain {len(people)} distinct named people spanning "
        f"approximately {latest_event - earliest_birth} years of recorded events. "
        "The main Gościński descendant network reaches nine supported generations; "
        "a provisional handwritten branch extends it to ten."
    )

    add_metric_table(
        doc,
        [
            ("Distinct people", str(summary["people"])),
            ("Supported depth", "9 generations"),
            ("Maximum width", f"{summary['confirmed_width']} people"),
            ("Recorded events", summary["event_range"]),
        ],
    )

    doc.add_heading("Scope and counting rules", level=1)
    add_bullets(
        doc,
        [
            "A person is counted once after duplicate appearances across the six charts are reconciled.",
            "Spouses and people in side pedigrees are included, even when they are not blood descendants of the main Gościński line.",
            f"{unknown_surname_count} people have no reliably readable surname; they remain in the people and first-name totals but appear as Unknown in the surname table.",
            f"At least {uncertain_count} records carry a provisional name, placement, or relationship note. Uncertainty is not converted into a false precision adjustment.",
            "Masculine and feminine Polish surname forms are combined for family-name counts, such as Gościński with Gościńska and Wiśniewski with Wiśniewska.",
            "Tree depth and width count descendants, not spouses. The supported measure excludes relationships explicitly marked uncertain; the inclusive measure adds the provisional handwritten placements.",
        ],
    )

    doc.add_heading("Tree size and shape", level=1)
    add_table(
        doc,
        ["Measure", "Supported relationships", "Including provisional relationships"],
        [
            ["Tree depth", "9 generations", "10 generations"],
            ["Longest path", "8 parent-child steps", "9 parent-child steps"],
            ["Maximum tree width", f"{summary['confirmed_width']} people in one generation", f"{summary['inclusive_width']} people in one generation"],
            ["People represented", f"{len(people)} total registry entries", f"Same {len(people)} people; placement differs"],
        ],
        widths=[2.0, 2.35, 2.35],
    )
    p = doc.add_paragraph()
    p.add_run("Interpretation. ").bold = True
    p.add_run(
        "The nine-generation supported path runs from Wawrzyniec Gościński (about 1760) "
        "through the modern Gościński branch to the grandchildren shown in the polished family tree. "
        "The tenth generation depends on the handwritten placement of Emilia Pawlowska below Jakub."
    )

    doc.add_heading("Date coverage", level=1)
    add_table(
        doc,
        ["Date measure", "Range", "Span", "Coverage"],
        [
            ["Known or approximate birth years", summary["birth_range"], f"{latest_birth - earliest_birth} years", f"{len(dated_births)} of {len(people)} people"],
            ["All recorded birth and death events", summary["event_range"], f"{latest_event - earliest_birth} years", "Latest event is a death in 2024"],
        ],
        widths=[2.0, 1.35, 1.0, 2.35],
    )

    doc.add_heading("Parent age when children were born", level=1)
    doc.add_paragraph(
        "Parent age is calculated as the child’s recorded birth year minus the recorded birth year "
        "of the parent. It is an approximate whole-year measure and includes only parent-child links "
        "with both years recorded. Father and mother describe the recorded family-registry role."
    )
    add_table(
        doc,
        ["Parent role", "Observations", "Mean", "Median", "Observed range", "Year coverage"],
        [
            ["Father", summary["father_age_count"], f"{summary['father_age_mean']:.1f}", f"{summary['father_age_median']:.0f}", f"{summary['father_age_min']}–{summary['father_age_max']}", f"{summary['father_age_count']} of {summary['father_age_coverage']} links"],
            ["Mother", summary["mother_age_count"], f"{summary['mother_age_mean']:.1f}", f"{summary['mother_age_median']:.0f}", f"{summary['mother_age_min']}–{summary['mother_age_max']}", f"{summary['mother_age_count']} of {summary['mother_age_coverage']} links"],
            ["Combined", summary["parent_age_count"], f"{summary['parent_age_mean']:.1f}", f"{summary['parent_age_median']:.0f}", f"{summary['parent_age_min']}–{summary['parent_age_max']}", "Recorded birth years only"],
        ],
        widths=[1.1, 0.9, 0.7, 0.7, 1.1, 2.0],
    )
    add_table(doc, ["Parent age", "Parent-child observations"], parent_age_distribution, widths=[2.2, 2.6])

    doc.add_heading("People by family name", level=1)
    surname_rows = sorted(surname_counts.items(), key=lambda item: (-item[1], item[0]))
    surname_midpoint = (len(surname_rows) + 1) // 2
    surname_left = surname_rows[:surname_midpoint]
    surname_right = surname_rows[surname_midpoint:]
    paired_surnames = []
    for index in range(surname_midpoint):
        left_name, left_count = surname_left[index]
        if index < len(surname_right):
            right_name, right_count = surname_right[index]
        else:
            right_name, right_count = "", ""
        paired_surnames.append([left_name, left_count, right_name, right_count])
    add_table(
        doc,
        ["Family name group", "People", "Family name group", "People"],
        paired_surnames,
        widths=[2.35, 0.7, 2.35, 0.7],
    )

    doc.add_heading("Most common first names", level=1)
    first_rows = sorted(first_counts.items(), key=lambda item: (-item[1], item[0]))
    top_first_rows = first_rows[:10]
    first_midpoint = (len(top_first_rows) + 1) // 2
    first_left = top_first_rows[:first_midpoint]
    first_right = top_first_rows[first_midpoint:]
    paired_first_names = []
    for index in range(first_midpoint):
        left_name, left_count = first_left[index]
        if index < len(first_right):
            right_name, right_count = first_right[index]
        else:
            right_name, right_count = "", ""
        paired_first_names.append([left_name, left_count, right_name, right_count])
    add_table(
        doc,
        ["First name", "People", "First name", "People"],
        paired_first_names,
        widths=[2.35, 0.7, 2.35, 0.7],
    )
    p = doc.add_paragraph()
    p.add_run("Most frequent. ").bold = True
    leaders = ", ".join(f"{name} ({count})" for name, count in first_rows[:6])
    p.add_run(leaders + ".")

    doc.add_page_break()
    doc.add_heading("Oldest people with recorded birth years", level=1)
    oldest = sorted(dated_births, key=lambda p: (p["birth"], p["first"], p["surname"]))[:10]
    oldest_rows = []
    for person in oldest:
        full_name = f"{person['first']} {person['surname']}".strip()
        birth = f"about {person['birth']}" if person["birth"] == 1760 else str(person["birth"])
        lifespan = birth
        if person["death"]:
            lifespan += f"–{person['death']}"
        oldest_rows.append([full_name, lifespan, person["note"] or "—"])
    add_table(
        doc,
        ["Person", "Recorded years", "Qualification"],
        oldest_rows,
        widths=[2.8, 1.3, 2.6],
    )

    doc.add_heading("What the statistics do not establish", level=1)
    doc.add_paragraph(
        "These counts describe the supplied charts, not the complete historical families. "
        "A missing person in a chart is not evidence that the person did not exist. Several printed "
        "side pedigrees use dashed connectors, and recent handwritten pages contain overwritten or "
        "unclear labels. Parish and civil records are needed to confirm disputed parentage, spellings, "
        "dates, and whether similarly named people are distinct."
    )

    doc.add_heading("Source files", level=1)
    add_bullets(
        doc,
        [
            "Drzewo Genealogy.png",
            "Goscinscy z Wapiennego Genealogy.png",
            "Goscinski z Pyrc Genealogy.png",
            "Mickulska Genealogy.png",
            "Rodzina Ramsow Geneoaogy.png",
            "Wladusklana Mickulska Genealogy.png",
            "Merged family-tree outline and English chart transcription in docs/genealogy.",
        ],
    )

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("Combined Muszyna genealogy statistics • working source synthesis")
    for run in footer.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(96, 96, 96)

    output_path = OUTPUT_DIR / "genealogy_statistics.docx"
    doc.save(output_path)

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
            "Counts reconcile duplicate appearances across all six charts. Spouses and side-pedigree people are included. Surname groups combine masculine and feminine Polish forms. People lacking a readable surname remain in the total and first-name counts. Depth and width exclude spouses and are reported both with and without explicitly provisional relationships. Gender, relationship, family-size, and lifespan measures are chart-derived summaries rather than complete civil-record measures; their scope and qualifications are stated above.",
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
    build_document()
