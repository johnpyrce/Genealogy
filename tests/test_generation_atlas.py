"""Regression coverage for the lineage atlas layout and safe HTML embedding."""

import json
import unittest

from scripts.build_generation_atlas_views import (
    TEMPLATE,
    atlas_layout,
    build_data,
    render_html,
)
from scripts.build_generation_overview import generation_layout
from scripts.lib.genealogy_data import load_families, load_people


def person(person_id, name="Test"):
    return dict(id=person_id, first=name, surname="Family", surname_group="Family",
                birth=None, death=None, note="", source="test")


class AtlasLayoutTests(unittest.TestCase):
    def test_synthetic_tree_orders_partners_then_children(self):
        people = [person(i) for i in range(1, 9)]
        families = [
            (1, 2, [3, 4], ""),   # root union
            (3, 5, [6], ""),      # child with own union
            (4, None, [7], ""),   # single-parent family
            # person 8 has no family links: disconnected
        ]
        layout = atlas_layout(people, families)
        order = [pid for pid, _ in sorted(layout.items(), key=lambda kv: kv[1]["row"])]
        self.assertEqual(len(order), 8)
        self.assertLess(order.index(1), order.index(3))
        self.assertLess(order.index(3), order.index(6))
        self.assertEqual(abs(order.index(1) - order.index(2)), 1)  # partners adjacent
        self.assertEqual(abs(order.index(3) - order.index(5)), 1)
        self.assertEqual(layout[6]["column"], 2)                   # generation 3 -> column 2
        self.assertEqual(order[-1], 8)                             # unaligned placed last
        self.assertEqual(layout[8]["column"], 3)                   # column after Gen 3

    def test_every_registry_person_placed_once(self):
        people = load_people()
        layout = atlas_layout(people, load_families())
        self.assertEqual(sorted(layout), sorted(p["id"] for p in people))
        rows = [p["row"] for p in layout.values()]
        self.assertEqual(len(rows), len(set(rows)))

    def test_columns_match_overview_generations(self):
        people = load_people()
        families = load_families()
        placements = generation_layout(people, families)
        generations = max(p["generation"] for p in placements.values())
        for p in build_data()["people"]:
            expected = placements[p["id"]]["generation"]
            self.assertEqual(p["generation"], expected)
            self.assertEqual(p["column"], expected - 1 if expected else generations)

    def test_payload_cannot_escape_script_and_preserves_unicode(self):
        name = 'Gościński </script><script>alert("x")</script> &'
        payload = json.dumps(
            {"people": [dict(person(1, name), column=0, row=0, generation=1,
                             alignment="aligned", component=1)],
             "families": [], "groups": ["Family"], "generations": 1,
             "columns": 1, "unions": 0},
            ensure_ascii=False).replace("<", "\\u003c")
        html = render_html(payload)
        self.assertNotIn("__ATLAS_DATA__", html)
        embedded = html.split("const data=", 1)[1].split(";\n", 1)[0]
        self.assertNotIn("<", embedded)
        self.assertEqual(json.loads(embedded)["people"][0]["first"], name)


class ViewsAtlasTests(unittest.TestCase):
    def test_render_is_safe_and_complete(self):
        payload = json.dumps(build_data(), ensure_ascii=False).replace("<", "\\u003c")
        html = render_html(payload)
        self.assertNotIn("__ATLAS_DATA__", html)
        embedded = html.split("const data=", 1)[1].split(";\n", 1)[0]
        self.assertNotIn("<", embedded)
        self.assertEqual(len(json.loads(embedded)["people"]), len(load_people()))

    def test_contains_all_three_renderers(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        for marker in ['data-view="labels"', 'data-view="dots"', 'data-view="line"',
                       "svgLabels", "svgDots", "svgLine", "markFor", "genBounds"]:
            self.assertIn(marker, template)

    def test_lifeline_axis_ends_at_current_year(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("new Date().getFullYear()", template)
        self.assertIn("Math.min(p.birth+40,yearMax)", template)
        self.assertNotIn("yearMax=Math.max(yearMax,p.birth+40)", template)

    def test_lifeline_nodate_lines_anchor_to_generation(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("genAnchor[p.generation]", template)
        self.assertIn("genBounds", template)
        self.assertIn("laneNeeded", template)
        self.assertIn("No generation · no dates", template)
        # every aligned generation has recorded births to anchor to
        data = build_data()
        for gen in {p["generation"] for p in data["people"] if p["generation"] > 0}:
            self.assertTrue(
                any(p["generation"] == gen and p["birth"] is not None
                    for p in data["people"]),
                f"generation {gen} has no recorded birth year to anchor to")


if __name__ == "__main__":
    unittest.main()
