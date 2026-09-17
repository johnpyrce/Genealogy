"""Regression coverage for the Cytoscape graph viewer and its help page."""

import unittest

from scripts.build_cytoscape_genealogy_graph import render_help, render_html


class CytoscapeGenealogyGraphTests(unittest.TestCase):
    def test_viewer_and_help_page_link_to_each_other(self):
        html = render_html({"people": [], "families": [], "evidence": [], "sources": []})
        help_page = render_help()

        self.assertIn('href="genealogy_relationship_graph_help.html"', html)
        self.assertNotIn("__GRAPH_DATA__", html)
        self.assertNotIn("__GRAPH_HELP_FILE__", html)
        self.assertIn('href="genealogy_relationship_graph.html"', help_page)
        self.assertNotIn("__GRAPH_FILE__", help_page)


if __name__ == "__main__":
    unittest.main()
