"""Regression coverage for import identity, provenance, and safe registry writes."""

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import validate_genealogy_data
from scripts.import_gedcom import (
    DEFAULT_INPUT, REGISTRY_PATHS, apply_plan, event_year, load_decisions,
    make_plan, parse_gedcom,
)
from scripts.lib.genealogy_data import ROOT, load_registry_csv
from scripts.lib import genealogy_data


class GedcomImportTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "artifacts").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "artifacts")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.registries = self.directory / "registries"
        self.registries.mkdir()
        for path in REGISTRY_PATHS:
            shutil.copyfile(path, self.registries / path.name)
        self.decisions = load_decisions(ROOT / "docs/imports/PyrceFamily.matches.json")

    def fixture(self, text):
        path = self.directory / "fixture.ged"
        path.write_text("0 HEAD\n1 CHAR UTF-8\n" + text + "0 TRLR\n", encoding="utf-8")
        return path

    @unittest.skipUnless(DEFAULT_INPUT.is_file(), "Original GEDCOM is intentionally untracked")
    def test_project_preview_preserves_files_and_reports_expected_overlap(self):
        original = {path.name: (self.registries / path.name).read_bytes() for path in REGISTRY_PATHS}
        plan = make_plan(DEFAULT_INPUT, self.registries, self.decisions)
        report = plan["report"]
        self.assertTrue(report["ready"])
        self.assertEqual(len(report["people_matched"]), 9)
        self.assertEqual(len(report["people_added"]), 56)
        self.assertEqual(len(report["families_added"]), 21)
        self.assertEqual([row["id"] for row in report["families_matched"]], [6, 25])
        self.assertEqual(len(report["conflicts"]), 2)
        for name, content in original.items():
            self.assertEqual((self.registries / name).read_bytes(), content)

    @unittest.skipUnless(DEFAULT_INPUT.is_file(), "Original GEDCOM is intentionally untracked")
    def test_apply_to_temporary_copy_preserves_facts_and_is_idempotent(self):
        _, before_people = load_registry_csv(self.registries / "people.csv")
        _, before_families = load_registry_csv(self.registries / "families.csv")
        plan = make_plan(DEFAULT_INPUT, self.registries, self.decisions)
        apply_plan(plan)
        _, people = load_registry_csv(self.registries / "people.csv")
        _, families = load_registry_csv(self.registries / "families.csv")
        self.assertEqual(people[:len(before_people)], before_people)
        self.assertEqual(families[:len(before_families)], before_families)
        self.assertEqual(len(people), len(before_people) + 56)
        self.assertEqual(len(families), len(before_families) + 21)
        self.assertEqual([row["id"] for row in families], [str(i) for i in range(1, len(families) + 1)])
        # Importing a subset must not attribute all existing siblings to this GEDCOM.
        _, evidence = load_registry_csv(self.registries / "relationship_evidence.csv")
        imported = [row for row in evidence if row["source_id"] == plan["report"]["source_id"]]
        self.assertTrue(all(row["relationship"] != "family" for row in imported if row["family_id"] == "6"))
        self.assertEqual({row["related_person_id"] for row in imported
                          if row["family_id"] == "6" and row["relationship"] == "parent-child"}, {"22"})
        _, evidence = load_registry_csv(self.registries / "person_source_evidence.csv")
        sophie = next(row for row in evidence if row["location"] == "GEDCOM @I1@")
        self.assertEqual(sophie["person_id"], "22")
        self.assertIn("1 MAY 1893", sophie["transcription"])
        self.assertIn("Muszyna, Nowy Sącz", sophie["transcription"])
        josef = next(row for row in evidence if row["source_id"] == plan["report"]["source_id"] and row["person_id"] == "78")
        self.assertIn("BET 1930 AND 1940", josef["transcription"])
        paths = {name: self.registries / getattr(genealogy_data, name).name for name in (
            "PEOPLE_REGISTRY", "FAMILY_REGISTRY", "SOURCE_REGISTRY", "EVIDENCE_REGISTRY", "PERSON_SOURCE_REGISTRY")}
        with patch.multiple(genealogy_data, **paths), patch.multiple(validate_genealogy_data,
                PEOPLE_REGISTRY=paths["PEOPLE_REGISTRY"], FAMILY_REGISTRY=paths["FAMILY_REGISTRY"]), redirect_stdout(io.StringIO()):
            validate_genealogy_data.main()
        again = make_plan(DEFAULT_INPUT, self.registries, self.decisions)
        self.assertEqual(again["changed"], {})
        self.assertEqual(again["report"]["people_added"], [])
        self.assertEqual(again["report"]["families_added"], [])

    def test_unique_name_and_date_match_retains_polish_spelling(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Jan /Goscinski/\n1 BIRT\n2 DATE 27 MAY 1888\n")
        plan = make_plan(path, self.registries)
        self.assertEqual(plan["report"]["people_matched"][0]["id"], 14)
        self.assertNotIn("people.csv", plan["changed"])

    def test_ambiguous_or_conflicting_names_require_explicit_decision(self):
        for text in (
            "0 @I1@ INDI\n1 NAME Jan /Goscinski/\n",
            "0 @I1@ INDI\n1 NAME Zofia /Goscinska/\n1 BIRT\n2 DATE 1893\n",
        ):
            with self.subTest(text=text):
                plan = make_plan(self.fixture(text), self.registries)
                self.assertFalse(plan["report"]["ready"])
                with self.assertRaisesRegex(ValueError, "Resolve"):
                    apply_plan(plan)
                added = make_plan(self.fixture(text), self.registries, {})
                self.assertTrue(added["report"]["ready"])
                self.assertEqual(len(added["report"]["people_added"]), 1)

    def test_qualified_dates_are_preserved_without_inventing_a_year(self):
        for date in ("ABT 1893", "BET 1930 AND 1940", "BEF 1940", "FROM 1930 TO 1940", "1893/1894"):
            with self.subTest(date=date):
                path = self.fixture(f"0 @I1@ INDI\n1 NAME Test /Surname/\n1 DEAT\n2 DATE {date}\n")
                record = next(row for row in parse_gedcom(path) if row.tag == "INDI")
                self.assertEqual(event_year(record, "DEAT"), "")
                plan = make_plan(path, self.registries)
                self.assertEqual(plan["report"]["people_added"][0]["death_year"], "")
                self.assertIn(date, plan["changed"]["person_source_evidence.csv"].decode())

    def test_parser_rejects_broken_references_duplicates_and_levels(self):
        for text in (
            "0 @I1@ INDI\n0 @F1@ FAM\n1 HUSB @I404@\n",
            "0 @I1@ INDI\n0 @I1@ INDI\n",
            "0 @I1@ INDI\n3 DATE 1900\n",
            "0 @I1@ INDI\n1 FAMC @F404@\n",
            "0 @I1@ INDI\n0 @F1@ FAM\n1 HUSB @I1@\n1 CHIL @I1@\n",
            "0 @I1@ INDI\n1 FAMC @F1@\n0 @F1@ FAM\n1 HUSB @I1@\n",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                make_plan(self.fixture(text), self.registries)

    def test_continuations_and_original_notes_are_retained(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Łucja /Żółć/\n1 NOTE First\n2 CONT second\n2 CONC third\n")
        record = next(row for row in parse_gedcom(path) if row.tag == "INDI")
        self.assertEqual(record.get("NOTE"), "First\nsecondthird")
        plan = make_plan(path, self.registries)
        self.assertIn("2 CONT second", plan["changed"]["person_source_evidence.csv"].decode())
        self.assertEqual(plan["report"]["people_added"][0]["surname"], "Żółć")

    def test_invalid_mapping_and_duplicate_targets_fail_before_writing(self):
        path = self.fixture("0 @I1@ INDI\n0 @I2@ INDI\n")
        for decisions in ({"@I1@": 999999}, {"@I404@": 10}, {"@I1@": 10, "@I2@": 10}):
            with self.subTest(decisions=decisions), self.assertRaises(ValueError):
                make_plan(path, self.registries, decisions)

    def test_stale_plan_and_changed_source_are_rejected(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Test /Surname/\n")
        plan = make_plan(path, self.registries)
        (self.registries / "people.csv").write_bytes(plan["originals"]["people.csv"] + b"\n")
        with self.assertRaisesRegex(ValueError, "changed after planning"):
            apply_plan(plan)
        (self.registries / "people.csv").write_bytes(plan["originals"]["people.csv"])
        apply_plan(plan)
        path.write_text(path.read_text().replace("Test", "Changed"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "content changed"):
            make_plan(path, self.registries)

    def test_write_failure_restores_previously_replaced_registries(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Test /Surname/\n")
        plan = make_plan(path, self.registries)
        replace = Path.replace
        count = 0

        def fail_second(source, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated disk failure")
            return replace(source, target)

        with patch.object(Path, "replace", fail_second), self.assertRaisesRegex(OSError, "disk failure"):
            apply_plan(plan)
        for name, content in plan["originals"].items():
            self.assertEqual((self.registries / name).read_bytes(), content)

    def test_new_person_decision_is_idempotent_without_project_gedcom(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Test /Surname/\n1 BIRT\n2 DATE 1990\n")
        decisions = {}
        apply_plan(make_plan(path, self.registries, decisions))
        self.assertEqual(make_plan(path, self.registries, decisions)["changed"], {})

    def test_previously_matched_identity_cannot_silently_be_changed_to_new(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Jan /Goscinski/\n1 BIRT\n2 DATE 1888\n")
        apply_plan(make_plan(path, self.registries, {"@I1@": 14}))
        with self.assertRaisesRegex(ValueError, "contradicts a previous import"):
            make_plan(path, self.registries, {})

    def test_decisions_reject_a_different_gedcom_version(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Test /Surname/\n")
        decisions = self.directory / "matches.json"
        decisions.write_text(json.dumps({"gedcom_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                         "people": {}}), encoding="utf-8")
        self.assertEqual(load_decisions(decisions, path), {})
        path.write_text(path.read_text(encoding="utf-8").replace("Test", "Changed"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different GEDCOM version"):
            load_decisions(decisions, path)

    def test_alternative_parentage_is_preserved_in_separate_families(self):
        path = self.fixture(
            "0 @I1@ INDI\n1 NAME Father /Alpha/\n"
            "0 @I2@ INDI\n1 NAME Father /Beta/\n"
            "0 @I3@ INDI\n1 NAME Mother /Gamma/\n"
            "0 @I4@ INDI\n1 NAME Child /Delta/\n"
            "0 @F1@ FAM\n1 HUSB @I1@\n1 WIFE @I3@\n1 CHIL @I4@\n"
            "0 @F2@ FAM\n1 HUSB @I2@\n1 WIFE @I3@\n1 CHIL @I4@\n")
        plan = make_plan(path, self.registries)
        self.assertEqual(len(plan["report"]["families_added"]), 2)
        self.assertEqual(len(plan["report"]["conflicts"]), 1)
        apply_plan(plan)
        _, evidence = load_registry_csv(self.registries / "relationship_evidence.csv")
        self.assertTrue(any(row["confidence"] == "uncertain" and "Alternative parentage" in row["note"] for row in evidence))

    def test_supplied_file_adds_omitted_people_even_when_auto_match_would_exist(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Jan /Goscinski/\n1 BIRT\n2 DATE 1888\n")
        discovered = make_plan(path, self.registries, load_decisions(None))
        self.assertEqual(discovered["report"]["people_matched"][0]["id"], 14)
        reviewed = make_plan(path, self.registries, {})
        self.assertTrue(reviewed["report"]["ready"])
        self.assertEqual(reviewed["report"]["people_matched"], [])
        self.assertEqual(len(reviewed["report"]["people_added"]), 1)

    def test_only_listed_people_are_matched_and_others_are_added(self):
        path = self.fixture("0 @I1@ INDI\n1 NAME Jan /Goscinski/\n1 BIRT\n2 DATE 1888\n"
                            "0 @I2@ INDI\n1 NAME Zofia /Goscinska/\n1 BIRT\n2 DATE 1893\n")
        plan = make_plan(path, self.registries, {"@I1@": 14})
        self.assertTrue(plan["report"]["ready"])
        self.assertEqual([row["gedcom_id"] for row in plan["report"]["people_matched"]], ["@I1@"])
        self.assertEqual([row["gedcom_id"] for row in plan["report"]["people_added"]], ["@I2@"])

    def test_match_file_rejects_null_decisions(self):
        path = self.directory / "matches.json"
        path.write_text(json.dumps({"people": {"@I1@": None}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "omit new people"):
            load_decisions(path)


if __name__ == "__main__":
    unittest.main()
