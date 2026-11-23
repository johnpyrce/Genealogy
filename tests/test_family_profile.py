"""Regression coverage for the standalone family profile computation and HTML."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts.build_family_profile import (
    TEMPLATE,
    build_data,
    compute_segments,
    load_families_with_roles,
    render_html,
)
from scripts.build_generation_overview import generation_layout
from scripts.lib.genealogy_data import load_people

GEDCOM = """0 HEAD
1 CHAR UTF-8
0 @P1@ INDI
1 NAME Jan /Żak/
1 BIRT
2 DATE 1900
0 @P2@ INDI
1 NAME Anna /Żak/
1 BIRT
2 DATE ABT 1930
0 @P3@ INDI
1 NAME Maria /Rams/
0 @F9@ FAM
1 WIFE @P1@
1 CHIL @P2@
0 TRLR
"""


def person(person_id, name="Test", group="Test", birth=None, death=None):
    return dict(id=person_id, first=name, surname=name, surname_group=group,
                birth=birth, death=death, note="", source="test")


class SegmentComputationTests(unittest.TestCase):
    def test_single_chain_assigns_one_segment_including_partner(self):
        people = [person(i, group="Line") for i in (1, 2, 3, 4, 5)]
        families = [
            (1, 2, [3], "main_line"),
            (3, 5, [4], "main_line"),
        ]
        placements = generation_layout(people, families)
        assignment, segments, inconsistencies = compute_segments(people, families, placements)
        self.assertEqual(assignment, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["label"], "Test Test")
        self.assertEqual(inconsistencies, [])

    def test_two_disjoint_main_lines_make_two_segments(self):
        people = [person(i, group="A" if i < 5 else "B") for i in range(1, 11)]
        families = [
            (1, None, [2], "main_line"),
            (2, None, [3], "main_line"),
            (6, None, [7], "main_line"),
            (7, None, [8], "main_line"),
        ]
        placements = generation_layout(people, families)
        assignment, segments, inconsistencies = compute_segments(people, families, placements)
        self.assertEqual(assignment[1], assignment[3])
        self.assertEqual(assignment[6], assignment[8])
        self.assertNotEqual(assignment[1], assignment[6])
        self.assertEqual(len(segments), 2)
        self.assertEqual(inconsistencies, [])

    def test_contradictory_main_line_cycle_is_reported_not_assigned(self):
        people = [person(i, group="Loop") for i in (1, 2, 3, 4)]
        families = [
            (1, None, [3], "main_line"),
            (3, None, [1], "main_line"),  # cycle: each heads and is child
        ]
        placements = generation_layout(people, families)
        assignment, segments, inconsistencies = compute_segments(people, families, placements)
        self.assertEqual(assignment, {})
        self.assertEqual(segments, [])
        self.assertEqual({i["person"] for i in inconsistencies}, {1, 3})
        for item in inconsistencies:
            self.assertIn(1, item["child_of"] + item["heads"])

    def test_non_main_line_families_are_never_assigned(self):
        people = [person(i, group="Side") for i in (1, 2, 3, 4)]
        families = [
            (1, None, [2], "collateral"),
            (3, None, [4], "spouse_ancestry"),
        ]
        placements = generation_layout(people, families)
        assignment, segments, inconsistencies = compute_segments(people, families, placements)
        self.assertEqual(assignment, {})
        self.assertEqual(segments, [])
        self.assertEqual(inconsistencies, [])

    def test_registry_families_carry_branch_roles(self):
        roles = {row[3] for row in load_families_with_roles()}
        self.assertEqual(roles, {"main_line", "collateral", "spouse_ancestry"})


class ProfileDataTests(unittest.TestCase):
    def test_gedcom_cli_builds_profile_from_file(self):
        with TemporaryDirectory() as directory:
            gedcom = Path(directory) / "tree.ged"
            output = Path(directory) / "profile.html"
            gedcom.write_text(GEDCOM, encoding="utf-8")
            command = [sys.executable, "-m", "scripts.build_family_profile", "--gedcom", str(gedcom)]
            subprocess.run([*command, "--output", str(output)], check=True, capture_output=True)
            html = output.read_text(encoding="utf-8")
            data = json.loads(html.split("const data=", 1)[1].split(";\n", 1)[0])
            self.assertEqual(data["gedcom"], "tree.ged")
            self.assertEqual(
                [(p["first"], p["group"], p["birth"], p["generation"]) for p in data["people"]],
                [("Jan", "Żak", 1900, 1), ("Anna", "Żak", None, 2), ("Maria", "Rams", None, 0)],
            )
            self.assertEqual(data["families"], [
                {"id": 1, "parents": [1], "children": [2], "role": None, "reference": "@F9@"},
            ])
            self.assertEqual(data["segments"], [])
            self.assertEqual(gedcom.read_text(encoding="utf-8"), GEDCOM)

            gedcom.write_text(GEDCOM.replace("1 CHIL @P2@", "1 CHIL @missing@"), encoding="utf-8")
            result = subprocess.run([*command, "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown person reference", result.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), html)

    def test_payload_covers_every_person_exactly_once(self):
        data = build_data()
        registry_ids = {p["id"] for p in load_people()}
        self.assertEqual({p["id"] for p in data["people"]}, registry_ids)
        for p in data["people"]:
            self.assertTrue(
                p["segment"] is None or 0 <= p["segment"] < len(data["segments"]),
                f"segment out of range for person {p['id']}")
        self.assertEqual(len(data["families"]), 88)
        self.assertTrue(all("role" in f for f in data["families"]))

    def test_payload_totals_are_consistent(self):
        data = build_data()
        main_members = sum(s["members"] for s in data["segments"])
        self.assertEqual(main_members, data["stats"]["main_line_people"])
        self.assertEqual(main_members,
                         sum(1 for p in data["people"] if p["segment"] is not None))
        self.assertEqual(sum(p["generation"] == 0 for p in data["people"]),
                         data["gaps"]["unaligned"])
        self.assertEqual(sum(p["birth"] is None for p in data["people"]),
                         data["gaps"]["undated"])
        self.assertEqual(sum(data["birth_decades"].values()), data["stats"]["dated"])

    def test_render_is_safe_and_complete(self):
        payload = json.dumps(build_data(), ensure_ascii=False).replace("<", "\\u003c")
        html = render_html(payload)
        self.assertNotIn("__PROFILE_DATA__", html)
        self.assertNotIn('role="tablist"', html)
        embedded = html.split("const data=", 1)[1].split(";\n", 1)[0]
        self.assertNotIn("<", embedded)
        self.assertEqual(len(json.loads(embedded)["people"]), len(load_people()))

    def test_template_has_all_lenses(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        for marker in ('id="ribbon"', 'id="genbars"', 'id="gaps"', 'id="matrix"',
                       'id="hist"', 'id="heat-key"', 'main-line segments',
                       'id="lens3"', 'id="lens4"', 'id="focusbar"',
                       'function applyFocus()', 'function renderHist('):
            self.assertIn(marker, template)

    def test_family_with_only_children_still_connects_siblings(self):
        placements = generation_layout(
            [person(i) for i in range(1, 4)],
            [(None, None, [2, 3], None)],
        )
        self.assertEqual(
            [(placements[i]["component"], placements[i]["generation"]) for i in (1, 2, 3)],
            [(1, 0), (2, 1), (2, 1)],
        )


if __name__ == "__main__":
    unittest.main()
