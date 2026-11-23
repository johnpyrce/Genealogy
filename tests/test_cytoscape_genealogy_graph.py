"""Regression coverage for the Cytoscape graph viewer and its help page."""

import unittest
import json
import shutil
import subprocess
from collections import defaultdict

from scripts.build_cytoscape_genealogy_graph import (
    add_person_sources, add_readable_family_evidence, dataset, render_help, render_html,
)


class CytoscapeGenealogyGraphTests(unittest.TestCase):
    def test_reference_generation_has_one_founding_family(self):
        families = {family["id"]: family for family in dataset()["families"]}
        self.assertEqual(
            [family["id"] for family in families.values() if family["generation"] == "1"],
            ["1"],
        )
        self.assertEqual([families[id]["generation"] for id in ("2", "44", "51")], ["2", "2", "2"])

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

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to execute browser export logic")
    def test_browser_exports_preserve_dates_alternative_families_and_filtered_members(self):
        html = render_html({"people": [], "families": [], "evidence": [], "sources": []})
        code = html[html.index("  function exportData()"):html.index("  function downloadExport(")]
        fixture = {
            "people": [
                {"id": "1", "first_name": "Józef", "surname": "Pyrć", "birth_year": "1816", "death_year": "", "note": "Approximate date"},
                {"id": "2", "first_name": "Zofia", "surname": "Gościńska", "birth_year": "", "death_year": "1902", "note": "First line\n0 @FAKE@ INDI"},
                {"id": "3", "first_name": "Jan", "surname": "Pyrć", "birth_year": "1852", "death_year": "1926"},
            ],
            "families": [
                {"id": "1", "father_id": "1", "mother_id": "2", "children": ["3"], "branch_role": "main_line", "note": "First account"},
                {"id": "2", "father_id": "1", "mother_id": "", "children": ["3"], "branch_role": "collateral", "note": "Alternative account"},
                {"id": "3", "father_id": "3", "mother_id": "", "children": ["1"], "branch_role": "collateral", "note": "Cycle retained"},
            ],
        }
        harness = r"""
const assert=require('node:assert/strict');
const document={getElementById:()=>({value:'all'})};
const fullName=p=>p.first_name+' '+p.surname;
const evidenceForCurrentSource=()=>[{source_id:'S1',confidence:'uncertain',relationship:'family',note:'Conflicting account'}];
const people=new Map(fixture.people.map(p=>[p.id,p]));
const activeData=()=>({activeFamilies:fixture.families,activePeople:new Set(['1','2','3'])});
let familyView=false;
const familiesMode=()=>familyView;
const personCategoryVisible=id=>id!=='2';
const text=textExport(fixture), ged=gedcomExport(fixture);
assert.match(text,/Józef Pyrć \(born 1816\)/);
assert.match(text,/Zofia Gościńska \(died 1902\)/);
assert.match(text,/born 1852; died 1926/);
assert.match(text,/expanded elsewhere/);
assert.match(text,/Alternative account/);
assert.match(ged,/1 FAMC @F1@\n1 FAMC @F2@/);
assert.match(ged,/1 BIRT\n2 DATE 1816/);
assert.match(ged,/2 CONT 0 @@FAKE@@ INDI/);
assert.ok(!ged.includes('\n0 @FAKE@ INDI'));
assert.ok(ged.endsWith('0 TRLR\n'));
const filtered=exportData();
assert.deepEqual(filtered.people.map(p=>p.id),['1','3']);
assert.equal(filtered.families[0].mother_id,'');
familyView=true;
const familyExport=exportData();
assert.deepEqual(familyExport.people.map(p=>p.id),['1','2','3']);
assert.equal(familyExport.families[0].mother_id,'2');
const individuals=new Set([...ged.matchAll(/^0 (@I\d+@) INDI$/gm)].map(m=>m[1]));
for(const match of ged.matchAll(/^1 (?:HUSB|WIFE|CHIL) (@I\d+@)$/gm))assert.ok(individuals.has(match[1]));
"""
        result = subprocess.run([shutil.which("node"), "-e", "const fixture=" + json.dumps(fixture) + ";\n" + code + harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

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
