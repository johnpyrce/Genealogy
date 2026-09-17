"""Regression tests for the reproducible DuckDB analytics layer."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import duckdb

from scripts import build_box_drawing_tree
from scripts.build_genealogy_analytics import build_output, create_tables, query_rows, supplemental_queries
from scripts.render_genealogy_analytics_report import render_report
from scripts.sync_genealogy_analytics_dashboard import reviewed_queries


class GenealogyAnalyticsTests(unittest.TestCase):
    def test_box_drawing_tree_is_rebuilt_from_csv_registries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "family_tree.md"
            original_output = build_box_drawing_tree.OUTPUT
            try:
                build_box_drawing_tree.OUTPUT = output
                build_box_drawing_tree.build()
            finally:
                build_box_drawing_tree.OUTPUT = original_output

            tree = output.read_text(encoding="utf-8")
            self.assertIn("generated directly from the editable people, family, source, and relationship-evidence CSV registries", tree)
            family_headings = re.findall(
                r"^[│ ]*[└├]── Family (\d+) ·", tree, flags=re.MULTILINE
            )
            self.assertEqual(len(family_headings), 63)
            self.assertEqual(len(set(family_headings)), 63)
            self.assertIn("Partner 1: Person 1 · Wawrzyniec Gościński (1760)", tree)
            self.assertRegex(tree, r"Person 14 · Jan Gościński \(1888–1970\)\n[│ ]*└── Family 8")
            self.assertIn(
                "Partner 2: Person 94 · Joanna Gruczelak (1901–1994) · ↪ child in Family 56",
                tree,
            )
            self.assertIn(
                "Person 15 · Marianna Miczulska (1895–1962) · ↪ also child in Family 63",
                tree,
            )
            self.assertIn("↪ Family 8 (expanded elsewhere)", tree)
            self.assertIn("People without a recorded family", tree)

    def test_box_drawing_tree_stops_at_a_family_cycle(self) -> None:
        people = {
            person_id: {
                "id": person_id,
                "first": f"Person{person_id}",
                "surname": "Test",
                "surname_group": "Test",
                "birth": None,
                "death": None,
                "source": "test",
                "note": "",
            }
            for person_id in range(1, 5)
        }
        families = [(1, 4, [2], ""), (2, 3, [1], "")]
        tree = build_box_drawing_tree.render_tree(
            people,
            families,
            {1: "main_line", 2: "main_line"},
            {1: ["S1"], 2: ["S1"]},
        )

        self.assertEqual(
            len(re.findall(r"^[│ ]*[└├]── Family \d+ ·", tree, flags=re.MULTILINE)),
            2,
        )
        self.assertIn("↪ Family 1 (expanded elsewhere)", tree)

    def test_normalized_grains_and_agreed_domains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "analytics.duckdb"
            connection = duckdb.connect(str(database))
            try:
                create_tables(connection)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM people").fetchone()[0], 164)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM family_children").fetchone()[0], 100)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM parent_child").fetchone()[0], 192)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM person_generation").fetchone()[0], 164)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM person_component").fetchone()[0], 164)

                output = build_output(connection)
                domains = {domain["id"]: domain["rows"] for domain in output["domains"]}
                self.assertEqual(
                    set(domains),
                    {
                        "inventory", "completeness", "evidence", "tree_structure",
                        "family_structure", "temporal", "names_and_identity",
                    },
                )
                tree_metrics = {row["measure"]: row["value"] for row in domains["tree_structure"]}
                self.assertEqual(tree_metrics["Maximum generation"], 9)
                completeness = {row["field"]: row for row in domains["completeness"]}
                self.assertEqual(completeness["Family evidence"]["total"], 63)
                self.assertEqual(completeness["Family evidence"]["coverage_pct"], 100.0)
                family_metrics = {row["measure"]: row["value"] for row in domains["family_structure"]}
                self.assertNotIn("People in sibling groups", family_metrics)
                self.assertNotIn("People with multiple recorded unions", family_metrics)
                report = render_report(connection)
                self.assertIn("## Executive summary", report)
                self.assertIn("## Evidence", report)
                self.assertIn("Maximum generation", report)
                self.assertNotIn("## Data quality", report)
                self.assertNotIn("## Research priorities", report)
                dashboard = reviewed_queries(connection)
                self.assertEqual(dashboard["summary"]["rows"][0]["maximumGeneration"], 9)
                self.assertEqual(dashboard["inventory"]["rows"][0]["measure"], "People")
                self.assertIn("source_contribution", dashboard)
                self.assertTrue(query_rows(connection, supplemental_queries()["family_size_distribution"]))
                self.assertTrue(query_rows(connection, supplemental_queries()["longevity_distribution"]))
                self.assertEqual(query_rows(connection, supplemental_queries()["top_first_names"])[0]["first_name"], "Jan")
                oldest_people = query_rows(connection, supplemental_queries()["oldest_people"])
                self.assertEqual(oldest_people[0]["person_name"], "Wawrzyniec Gościński")
                self.assertEqual(oldest_people[0]["birth_year"], 1760)
                self.assertEqual(dashboard["oldest_people"]["rows"][0]["birthYear"], "1760")
                self.assertIn("## Oldest people with recorded birth years", report)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
