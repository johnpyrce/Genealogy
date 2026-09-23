"""Regression coverage for the Cytoscape graph viewer and its help page."""

import unittest
from collections import defaultdict

from scripts.build_cytoscape_genealogy_graph import dataset, render_help, render_html


class CytoscapeGenealogyGraphTests(unittest.TestCase):
    def test_s5_source_projection_keeps_the_chart_connected(self):
        data = dataset()
        evidence_by_family = defaultdict(list)
        for row in data["evidence"]:
            if row["source_id"] == "S5":
                evidence_by_family[row["family_id"]].append(row)

        graph = defaultdict(set)
        for family in data["families"]:
            rows = evidence_by_family[family["id"]]
            if not rows:
                continue
            whole_family = any(row["relationship"] == "family" for row in rows)
            cited_children = {
                row["related_person_id"] for row in rows
                if row["relationship"] == "parent-child"
            }
            members = [family["father_id"], family["mother_id"]]
            members.extend(
                child for child in family["children_ids"].split(";")
                if child and (whole_family or child in cited_children)
            )
            members = [person_id for person_id in members if person_id]
            for person_id in members:
                graph[person_id].update(members)

        visited = set()
        pending = ["88"]  # Marcin Rams, at the left edge of S5.
        while pending:
            person_id = pending.pop()
            if person_id not in visited:
                visited.add(person_id)
                pending.extend(graph[person_id] - visited)

        self.assertEqual(visited, set(graph))
        self.assertEqual(len(visited), 51)
        self.assertIn("163", visited)  # Jan Miczulski joins the Gościński bridge.
        self.assertNotIn("97", graph)  # Józef Drost has no clear connector in S5.

    def test_viewer_and_help_page_link_to_each_other(self):
        html = render_html({"people": [], "families": [], "evidence": [], "sources": []})
        help_page = render_help()

        self.assertIn('href="genealogy_relationship_graph_help.html"', html)
        self.assertIn('id="layout"', html)
        self.assertIn('value="radial">Radial tree', html)
        self.assertIn('function radialLayout()', html)
        self.assertIn("const foundingFamilies=", html)
        self.assertIn("const subtreeWeight=", html)
        self.assertIn("const ringRanks=new Map", html)
        self.assertIn("radius=(ringRanks.get(node.id())-minimumRank+1)*ringGap/2", html)
        self.assertNotIn("radius=depth.get(node.id())*ringGap", html)
        self.assertIn("'width':28,'height':28", html)
        self.assertIn("node.person.radial-layout", html)
        self.assertIn("'width':40,'height':40", html)
        self.assertIn("boundingBox({includeLabels:false})", html)
        self.assertIn("overviewZoom=view.zoom", html)
        self.assertIn("Math.max(12,11/zoom)", html)
        self.assertNotIn("__GRAPH_DATA__", html)
        self.assertNotIn("__GRAPH_HELP_FILE__", html)
        self.assertIn('href="genealogy_relationship_graph.html"', help_page)
        self.assertIn('Radial tree', help_page)
        self.assertNotIn("__GRAPH_FILE__", help_page)


if __name__ == "__main__":
    unittest.main()
