"""Regression coverage for the Cytoscape graph viewer and its help page."""

import unittest
from collections import defaultdict

from scripts.build_cytoscape_genealogy_graph import (
    add_person_sources, add_readable_family_evidence, dataset, render_help, render_html,
)


class CytoscapeGenealogyGraphTests(unittest.TestCase):
    def test_source_colors_use_only_explicit_person_and_relationship_citations(self):
        people = [{'id': str(i)} for i in range(1, 6)]
        families = [{'id': '1', 'father_id': '1', 'mother_id': '2', 'children_ids': '3;4'}]
        evidence = [
            {'family_id': '1', 'source_id': 'S1', 'relationship': 'family'},
            {'family_id': '1', 'source_id': 'S2', 'relationship': 'parent-child',
             'person_id': '1', 'related_person_id': '3'},
        ]
        person_evidence = [{'person_id': '4', 'source_id': 'S7'}]
        add_person_sources(people, families, evidence, person_evidence)
        self.assertEqual([p['source_ids'] for p in people], ['S1;S2', 'S1', 'S1;S2', 'S1;S7', ''])

    def test_gedcom_family_summary_resolves_source_specific_names_and_preserves_raw_record(self):
        raw = '0 @F26@ FAM\n1 HUSB @I74@\n1 WIFE @I69@\n1 CHIL @I73@\n1 NOTE An alternative account'
        rows = [{'source_id': 'S7', 'transcription': raw, 'confidence': 'probable'}]
        people = [
            {'id': '1', 'first_name': 'Józef', 'surname': 'Pyrć'},
            {'id': '2', 'first_name': 'Zofia', 'surname': 'Gościńska'},
        ]
        identities = [
            {'source_id': 'S7', 'person_id': '1', 'location': 'GEDCOM @I74@'},
            {'source_id': 'S7', 'person_id': '2', 'location': 'GEDCOM @I69@'},
            {'source_id': 'S8', 'person_id': '1', 'location': 'GEDCOM @I73@'},
        ]
        add_readable_family_evidence(rows, people, identities)
        self.assertEqual(rows[0]['summary'], 'Husband: Józef Pyrć\nWife: Zofia Gościńska\nChild: Unresolved person @I73@')
        self.assertEqual(rows[0]['transcription'], raw)
        self.assertEqual(rows[0]['confidence'], 'probable')

    def test_ambiguous_gedcom_identity_is_not_silently_resolved(self):
        rows = [{'source_id': 'S7', 'transcription': '0 @F1@ FAM\n1 CHIL @I1@'}]
        people = [{'id': '1', 'first_name': 'Jan', 'surname': 'Pyrce'}]
        identities = [
            {'source_id': 'S7', 'person_id': person_id, 'location': 'GEDCOM @I1@'}
            for person_id in ['1', '2']
        ]
        add_readable_family_evidence(rows, people, identities)
        self.assertEqual(rows[0]['summary'], 'Child: Unresolved person @I1@')

    def test_chart_transcriptions_are_not_reinterpreted_as_gedcom(self):
        rows = [{'source_id': 'S1', 'transcription': 'Józef and Zofia with children'}]
        original = rows[0].copy()
        add_readable_family_evidence(rows, [], [])
        self.assertEqual(rows[0], original)

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
