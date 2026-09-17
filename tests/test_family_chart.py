"""Regression coverage for registry conversion and safe HTML embedding."""

import json
import re
import unittest

from scripts.build_family_chart import build_data, build_source_views, render_html
from scripts.lib.genealogy_data import load_families, load_people


def person(person_id, name="Test"):
    return dict(id=person_id, first=name, surname="Family", birth=None,
                death=None, note="", source="test")


class FamilyChartTests(unittest.TestCase):
    def test_multiple_spouses_single_parent_and_duplicate_links(self):
        rows = build_data([person(i) for i in range(1, 7)], [
            (1, 2, [4], ""), (1, 3, [5], ""), (1, 2, [4], ""),
            (None, 3, [6], ""),
        ])
        data = {p["id"]: p for p in rows}
        self.assertEqual(data["1"]["rels"],
                         dict(parents=[], spouses=["2", "3"], children=["4", "5"]))
        self.assertEqual(data["4"]["rels"]["parents"], ["1", "2"])
        self.assertEqual(data["6"]["rels"]["parents"], ["3"])
        self.assertEqual(data["6"]["data"]["gender"], "U")
        self.assertEqual(data["3"]["data"]["gender"], "F")

    def test_project_data_preserves_every_person_and_family_link(self):
        data = {p["id"]: p for p in build_data()}
        self.assertEqual(set(data), {str(p["id"]) for p in load_people()})
        for father, mother, children, _ in load_families():
            if father is not None and mother is not None:
                self.assertIn(str(mother), data[str(father)]["rels"]["spouses"])
                self.assertIn(str(father), data[str(mother)]["rels"]["spouses"])
            for parent in (father, mother):
                if parent is None:
                    continue
                for child in children:
                    self.assertIn(str(child), data[str(parent)]["rels"]["children"])
                    self.assertIn(str(parent), data[str(child)]["rels"]["parents"])

    def test_json_cannot_escape_script_and_preserves_unicode(self):
        name = 'Gościński </script><script>alert("x")</script> &'
        data = build_data([person(1, name)], [])
        html = render_html(data, "1")
        embedded = re.search(r'<script id="family-data" type="application/json">(.*?)</script>', html).group(1)
        self.assertNotIn("<", embedded)
        self.assertEqual(json.loads(embedded)["people"][0]["data"]["first name"], name)

    def test_viewer_links_to_its_companion_help_page(self):
        html = render_html(build_data([person(1)], []), "1")
        self.assertIn('href="family_tree_help.html"', html)
        self.assertNotIn("__FAMILY_HELP_FILE__", html)

    def test_invalid_graphs_fail_clearly(self):
        cases = [
            ([person(1)], [(1, 2, [], "")], "unknown person"),
            ([person(1), person(2)], [(1, None, [2], ""), (2, None, [1], "")], "cycle"),
            ([person(1), person(1)], [], "Duplicate"),
            ([], [], "empty"),
        ]
        for people, families, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                build_data(people, families)
        with self.assertRaisesRegex(ValueError, "Unknown root"):
            render_html(build_data([person(1)], []), "99")

    def test_alternative_parentage_preserves_both_accounts(self):
        rows = build_data([person(i) for i in range(1, 5)], [
            (1, 2, [4], "First source"), (3, None, [4], "Other source"),
        ])
        self.assertEqual(rows[3]["rels"]["parents"], ["1", "2", "3"])
        self.assertEqual(rows[3]["data"]["parentages"], [
            {"parents": ["1", "2"], "note": "First source"},
            {"parents": ["3"], "note": "Other source"},
        ])

    def test_family_name_group_is_embedded(self):
        row = person(1)
        row["surname_group"] = "Normalized family"
        self.assertEqual(build_data([row], [])[0]["data"]["family name"], "Normalized family")

    def test_detached_people_keep_document_provenance(self):
        project = {person["id"]: person for person in build_data()}
        self.assertEqual(project["17"]["data"]["source ids"], ["S2"])
        self.assertEqual(project["21"]["data"]["source ids"], ["S2"])
        self.assertEqual(project["97"]["data"]["source ids"], ["S5"])

    def test_source_views_preserve_only_supported_relationships(self):
        families = [(1, 2, [3, 4], "Family note"), (3, 5, [6], "Other")]
        evidence = [
            {"family_id": "1", "source_id": "S1", "relationship": "family", "related_person_id": ""},
            {"family_id": "1", "source_id": "S2", "relationship": "parent-child", "related_person_id": "3"},
            {"family_id": "2", "source_id": "S2", "relationship": "spouse", "related_person_id": "5"},
        ]
        views = build_source_views(families, evidence)
        self.assertEqual(views["S1"][0]["children"], ["3", "4"])
        self.assertEqual(views["S2"][0]["parents"], ["1", "2"])
        self.assertEqual(views["S2"][0]["children"], ["3"])
        self.assertEqual(views["S2"][1]["parents"], ["3", "5"])
        self.assertEqual(views["S2"][1]["children"], [])


if __name__ == "__main__":
    unittest.main()
