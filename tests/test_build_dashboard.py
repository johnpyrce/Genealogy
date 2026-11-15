"""Installed Data builder discovery across supported plugin layouts."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_dashboard import resolve_builder


class DashboardBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "plugins/cache/openai-curated-remote/data-analytics"
        environment = patch.dict(os.environ, {"CODEX_HOME": str(self.root), "CODEX_NODE": "/test/node"})
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("DATA_ANALYTICS_PLUGIN", None)

    def install(self, version, relative):
        builder = self.cache / version / relative / "scripts/data-app.mjs"
        builder.parent.mkdir(parents=True)
        builder.write_text("// Installed builder", encoding="utf-8")
        return builder

    def test_newest_usable_version_supports_nested_and_legacy_layouts(self):
        old = self.install("1.1.9", "")
        self.assertEqual(resolve_builder(), ("/test/node", old))
        newest = self.install("1.2.0", "output_formats/html")
        self.assertEqual(resolve_builder()[1], newest)
        self.install("1.10.0", "")
        self.assertEqual(resolve_builder()[1], self.cache / "1.10.0/scripts/data-app.mjs")
        (self.cache / "2.0.0").mkdir()
        with patch.dict(os.environ, {"DATA_ANALYTICS_PLUGIN": str(self.cache / "1.2.0")}):
            self.assertEqual(resolve_builder()[1], newest)
        with patch.dict(os.environ, {"DATA_ANALYTICS_PLUGIN": str(newest.parent.parent)}):
            self.assertEqual(resolve_builder()[1], newest)

    def test_invalid_explicit_override_does_not_fall_back(self):
        self.install("1.2.0", "output_formats/html")
        with patch.dict(os.environ, {"DATA_ANALYTICS_PLUGIN": str(self.root / "missing")}):
            with self.assertRaisesRegex(RuntimeError, "Installed Data builder not found"):
                resolve_builder()

    def test_missing_plugin_reports_actionable_error(self):
        with self.assertRaisesRegex(RuntimeError, "Installed Data builder not found"):
            resolve_builder()


if __name__ == "__main__":
    unittest.main()
