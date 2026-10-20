"""CLI fetch/preview provenance, matching and file-preservation checks."""
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import genealogy
from scripts.import_gedcom import load_decisions
from scripts.lib.genealogy_data import ROOT
from scripts.lib.rootsmagic_ui import AutomationError, Observation, RootsMagicUI


def gedcom(xref="@I1@", fsid="G4ZN-5FR", extra=""):
    return (f"0 HEAD\n1 CHAR UTF-8\n0 {xref} INDI\n1 NAME Sophie /Goscinski/\n"
            f"1 _FSFTID {fsid}\n1 BIRT\n2 DATE 1893\n1 DEAT\n2 DATE 1964\n{extra}0 TRLR\n")


class FetchTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "artifacts").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "artifacts")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.previous = self.directory / "previous.ged"
        self.previous.write_text(gedcom("@I8@"), encoding="utf-8")
        self.matches = self.directory / "previous.matches.json"
        self.matches.write_text(json.dumps({"people": {"@I8@": 22},
            "gedcom_sha256": hashlib.sha256(self.previous.read_bytes()).hexdigest(),
            "rationale": {"@I8@": "Proposed Sophie/Zofia match."}}), encoding="utf-8")
        self.current = self.directory / "current.ged"
        self.current.write_text(gedcom("@I99@"), encoding="utf-8")
        self.runs = self.directory / "runs"
        self.addCleanup(patch.stopall)
        patch.object(genealogy, "RUNS", self.runs).start()

    def test_previous_matches_follow_familysearch_ids_across_renumbering(self):
        matches, notes, warnings, new_people = genealogy.carry_matches(self.previous, self.matches, self.current)
        self.assertEqual(matches, {"@I99@": 22})
        self.assertIn("G4ZN-5FR", notes["@I99@"])
        self.assertEqual(warnings, [])
        self.assertEqual(new_people, set())

    def test_source_fingerprint_must_match_before_carrying_identities(self):
        self.previous.write_text(gedcom("@Ichanged@"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different GEDCOM version"):
            genealogy.carry_matches(self.previous, self.matches, self.current)

    def test_duplicate_familysearch_ids_are_not_silently_collapsed(self):
        self.current.write_text(gedcom("@I99@", extra="0 @I2@ INDI\n1 NAME Other /Person/\n1 _FSFTID G4ZN-5FR\n"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate FamilySearch ID"):
            genealogy.carry_matches(self.previous, self.matches, self.current)

    def test_export_counts_and_starting_person_are_verified(self):
        metadata = {"downloaded_people": 1, "downloaded_families": 0}
        self.assertEqual(genealogy.validate_export(self.current, "G4ZN-5FR", metadata)["people"], 1)
        with self.assertRaisesRegex(ValueError, "counts"):
            genealogy.validate_export(self.current, "G4ZN-5FR", dict(metadata, downloaded_people=2))
        with self.assertRaisesRegex(ValueError, "requested FamilySearch"):
            genealogy.validate_export(self.current, "AAAA-BBB", metadata)

    def test_preview_writes_sparse_matches_and_preserves_sources_and_registries(self):
        before = {path: path.read_bytes() for path in genealogy.REGISTRY_PATHS}
        before[self.previous] = self.previous.read_bytes()
        before[self.current] = self.current.read_bytes()
        with redirect_stdout(io.StringIO()):
            report = genealogy.prepare_preview(self.current, self.directory / "review", self.previous, self.matches)
        self.assertTrue(report["ready"])
        self.assertEqual([person["id"] for person in report["people_matched"]], [22])
        proposed = self.directory / "review/matches.json"
        self.assertEqual(load_decisions(proposed, self.current), {"@I99@": 22})
        self.assertTrue((self.directory / "review/preview.md").is_file())
        self.assertTrue((self.directory / "review/preview.json").is_file())
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_new_possible_overlap_stays_unresolved_while_known_matches_are_anchored(self):
        self.current.write_text(gedcom("@I99@", extra="0 @I2@ INDI\n1 NAME Jan /Goscinski/\n"), encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            report = genealogy.prepare_preview(self.current, self.directory / "review", self.previous, self.matches)
        self.assertFalse(report["ready"])
        self.assertEqual([row["gedcom_id"] for row in report["unresolved"]], ["@I2@"])
        self.assertEqual(report["people_added"], [])
        self.assertEqual(load_decisions(self.directory / "review/matches.json", self.current), {"@I99@": 22})

    def test_unique_runs_do_not_replace_existing_files(self):
        instant = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        job = genealogy.reserve_run("G4ZN-5FR", self.directory, now=instant)
        job["gedcom"].write_text("preserve this", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            genealogy.reserve_run("G4ZN-5FR", self.directory, now=instant)
        self.assertEqual(job["gedcom"].read_text(encoding="utf-8"), "preserve this")
        with self.assertRaisesRegex(ValueError, "outside the registries"):
            genealogy.reserve_run("G4ZN-5FR", genealogy.REGISTRIES)

    def test_second_fetch_cannot_take_the_same_repository_lock(self):
        with genealogy.fetch_lock(), self.assertRaisesRegex(AutomationError, "already running"):
            with genealogy.fetch_lock():
                self.fail("Second download acquired the lock")

    def test_fetch_pipeline_saves_manifest_and_preview_without_importing(self):
        class Download:
            def __init__(self, directory, app):
                self.directory = directory

            def fetch(self, person, ancestors, descendants, database, destination, timeout):
                database.write_bytes(b"test database")
                destination.write_text(gedcom("@I99@"), encoding="utf-8")
                return dict(version="12.1.1", downloaded_people=1, downloaded_families=0)

        with redirect_stdout(io.StringIO()):
            code = genealogy.fetch(self.arguments(), driver_factory=Download)
        self.assertEqual(code, 0)
        manifest = json.loads(next(self.runs.glob("*/download.json")).read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "preview_ready")
        self.assertFalse(manifest["registry_import_applied"])
        self.assertEqual(manifest["people_matched"], 1)
        self.assertTrue(next(self.runs.glob("*/preview.md")).is_file())

    def test_failure_keeps_diagnostic_manifest_and_preserves_export(self):
        class InterruptedDownload:
            def __init__(self, directory, app):
                pass

            def fetch(self, person, ancestors, descendants, database, destination, timeout):
                destination.write_text("partial export", encoding="utf-8")
                raise AutomationError("Unexpected RootsMagic dialog")

        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(AutomationError, "Unexpected"):
            genealogy.fetch(self.arguments(), driver_factory=InterruptedDownload)
        manifest = json.loads(next(self.runs.glob("*/download.json")).read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "failed")
        self.assertFalse(manifest["registry_import_applied"])
        self.assertEqual((ROOT / manifest["gedcom"]).read_text(encoding="utf-8"), "partial export")

    def arguments(self):
        return Namespace(person="G4ZN-5FR", ancestors=10, descendants=4, app=genealogy.DEFAULT_APP,
                         timeout=30, output_directory=self.directory, previous_gedcom=self.previous,
                         previous_matches=self.matches, no_previous_matches=False)

    def test_ocr_selection_rejects_ambiguous_labels_and_can_limit_to_sidebar(self):
        state = Observation(dict(window_title="RootsMagic", labels=[
            dict(text="File", x=20, y=80, width=30, height=14),
            dict(text="File", x=180, y=90, width=30, height=14),
        ]))
        with self.assertRaisesRegex(AutomationError, "found 2"):
            state.unique("File")
        self.assertEqual(state.unique("File", left_of=150)["x"], 20)

    def test_previously_omitted_person_stays_an_addition_after_renumbering(self):
        previous = gedcom("@I8@", extra="0 @I2@ INDI\n1 NAME Jan /Goscinski/\n1 _FSFTID AAAA-BBB\n")
        self.previous.write_text(previous, encoding="utf-8")
        metadata = json.loads(self.matches.read_text(encoding="utf-8"))
        metadata["gedcom_sha256"] = genealogy.digest(self.previous)
        self.matches.write_text(json.dumps(metadata), encoding="utf-8")
        self.current.write_text(gedcom("@I99@", extra="0 @I42@ INDI\n1 NAME Jan /Goscinski/\n1 _FSFTID AAAA-BBB\n"), encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            report = genealogy.prepare_preview(self.current, self.directory / "review", self.previous, self.matches)
        self.assertTrue(report["ready"])
        self.assertEqual([row["gedcom_id"] for row in report["people_added"]], ["@I42@"])

    def test_registry_stable_id_prevents_duplicate_additions_on_later_exports(self):
        evidence = [dict(location="GEDCOM @Iold@", person_id="22", transcription="0 @Iold@ INDI\n1 _FSFTID G4ZN-5FR\n")]
        with patch.object(genealogy, "load_person_source_evidence", return_value=evidence), redirect_stdout(io.StringIO()):
            report = genealogy.prepare_preview(self.current, self.directory / "review")
        self.assertTrue(report["ready"])
        self.assertEqual([row["id"] for row in report["people_matched"]], [22])
        self.assertEqual(report["people_added"], [])

    def test_conflicting_registry_stable_ids_require_reconciliation(self):
        evidence = [dict(location="GEDCOM @Iold@", person_id=str(person_id), transcription="1 _FSFTID G4ZN-5FR\n")
                    for person_id in (22, 23)]
        with patch.object(genealogy, "load_person_source_evidence", return_value=evidence), self.assertRaisesRegex(ValueError, "multiple registry"):
            genealogy.registry_familysearch_ids()

    def test_window_transition_retries_observation_without_replaying_input(self):
        ui = RootsMagicUI.__new__(RootsMagicUI)
        ui.directory = self.directory / "ui"
        ui.command = Mock(side_effect=[AutomationError("Window geometry is unavailable"),
                                      dict(window_title="RootsMagic 12", labels=[], fields=[])])
        with patch("scripts.lib.rootsmagic_ui.time.sleep"):
            self.assertEqual(ui.observe().data["window_title"], "RootsMagic 12")
        self.assertEqual([call.args[0] for call in ui.command.call_args_list], ["snapshot", "snapshot"])

    def test_permission_errors_are_reported_without_retrying(self):
        ui = RootsMagicUI.__new__(RootsMagicUI)
        ui.directory = self.directory / "ui"
        ui.command = Mock(side_effect=AutomationError("Enable Accessibility and Screen Recording"))
        with self.assertRaisesRegex(AutomationError, "Enable Accessibility"):
            ui.observe()
        self.assertEqual(ui.command.call_count, 1)


if __name__ == "__main__":
    unittest.main()
