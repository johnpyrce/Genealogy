"""Snapshot refresh protects other sources while replacing GEDCOM-owned data."""

from contextlib import redirect_stdout
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import validate_genealogy_data
from scripts.import_gedcom import REGISTRY_PATHS, apply_plan, make_plan, markdown_report
from scripts.lib import genealogy_data
from scripts.lib.gedcom_refresh import csv_bytes, make_refresh_plan, snapshot_path
from scripts.lib.genealogy_data import ROOT, load_registry_csv


def person(xref, fsid, first, surname="", birth="", death=""):
    return (f"0 {xref} INDI\n1 NAME {first} /{surname}/\n"
            + (f"1 _FSFTID {fsid}\n" if fsid else "")
            + (f"1 BIRT\n2 DATE {birth}\n" if birth else "")
            + (f"1 DEAT\n2 DATE {death}\n" if death else ""))


class GedcomRefreshTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "artifacts").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "artifacts")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.registries = self.directory / "registries"
        self.registries.mkdir()
        self.path = self.directory / "tree.ged"
        self.chart = self.directory / "chart.txt"
        self.chart.write_text("Original chart", encoding="utf-8")
        self.headers = {p.name: load_registry_csv(p)[0] for p in REGISTRY_PATHS}
        self.write("people.csv", [
            dict(id="1", first_name="Łucja", surname="Żółć", family_name_group="Żółć", birth_year="1900", source="printed", note="Original chart spelling"),
            dict(id="2", first_name="Jan", surname="Test", family_name_group="Test", birth_year="1899", source="printed"),
            dict(id="3", first_name="Dziecko", surname="Test", family_name_group="Test", birth_year="1920", source="printed"),
        ])
        self.write("families.csv", [dict(id="1", father_id="2", mother_id="1", children_ids="3", branch_role="main_line", note="Original chart family")])
        self.write("sources.csv", [dict(source_id="S1", file_name=self.chart.relative_to(ROOT).as_posix(), display_name="Original chart", source_type="printed chart")])
        self.write("relationship_evidence.csv", [dict(evidence_id="E001", family_id="1", relationship="parent-child", person_id="1", related_person_id="3", source_id="S1", confidence="confirmed", transcription="Original chart")])
        self.write("person_source_evidence.csv", [dict(person_id="1", source_id="S1", location="chart", transcription="Łucja Żółć 1900", confidence="confirmed")])
        self.initial = (
            person("@I1@", "AAAA-AAA", "Lucia", "Zolc", "1900")
            + person("@I2@", "BBBB-BBB", "Parent", "Example", "1920")
            + person("@I3@", "CCCC-CCC", "Child", birth="1950")
            + "0 @F1@ FAM\n1 WIFE @I1@\n1 CHIL @I2@\n"
            + "0 @F2@ FAM\n1 HUSB @I2@\n1 CHIL @I3@\n"
        )
        self.export(self.initial)
        self.initial_bytes = self.path.read_bytes()
        self.initial_hash = hashlib.sha256(self.initial_bytes).hexdigest()
        apply_plan(make_plan(self.path, self.registries, {"@I1@": 1}))

    def write(self, name, rows):
        headers = self.headers[name]
        rows = [dict(dict.fromkeys(headers, ""), **row) for row in rows]
        (self.registries / name).write_bytes(csv_bytes(headers, rows))

    def rows(self, name):
        return load_registry_csv(self.registries / name)[1]

    def export(self, body):
        self.path.write_text("0 HEAD\n1 CHAR UTF-8\n1 DATE 10 NOV 2026\n" + body + "0 TRLR\n", encoding="utf-8")

    def updated(self, include_child=True):
        return (person("@I7@", "AAAA-AAA", "Lucia", "Zolc", "1901", "1980")
                + person("@I8@", "BBBB-BBB", "Parent", "Changed", "1921")
                + (person("@I9@", "CCCC-CCC", "Child", "Found", "1950") if include_child else "")
                + person("@I10@", "FFFF-FFF", "New", "Child", "1952")
                + "0 @F77@ FAM\n1 WIFE @I7@\n1 CHIL @I8@\n"
                + "0 @F88@ FAM\n1 HUSB @I8@\n1 CHIL @I10@\n")

    def validate(self):
        paths = {name: self.registries / getattr(genealogy_data, name).name for name in (
            "PEOPLE_REGISTRY", "FAMILY_REGISTRY", "SOURCE_REGISTRY", "EVIDENCE_REGISTRY", "PERSON_SOURCE_REGISTRY")}
        with patch.multiple(genealogy_data, **paths), patch.multiple(validate_genealogy_data,
                PEOPLE_REGISTRY=paths["PEOPLE_REGISTRY"], FAMILY_REGISTRY=paths["FAMILY_REGISTRY"]), redirect_stdout(io.StringIO()):
            validate_genealogy_data.main()

    def test_preview_and_apply_replace_owned_facts_and_keep_chart_accounts(self):
        original = {p.name: (self.registries / p.name).read_bytes() for p in REGISTRY_PATHS}
        self.export(self.updated())
        plan = make_refresh_plan(self.path, self.registries)
        self.assertTrue(plan["report"]["ready"])
        for name, content in original.items():
            self.assertEqual((self.registries / name).read_bytes(), content)
        self.assertFalse(any(p.name.startswith("registries-") for p in self.directory.rglob("registries-*")))
        self.assertEqual({r["id"] for r in plan["report"]["people_updated"]}, {1, 4, 5})
        self.assertEqual(len(plan["report"]["families_removed"]), 1)
        self.assertEqual(len(plan["report"]["families_added"]), 1)
        plan["report"]["mode"] = "preview"
        rendered = markdown_report(plan["report"])
        self.assertIn("1920 → 1921", rendered)
        self.assertIn("Superseded families removed: 1", rendered)
        apply_plan(plan)
        people = {r["id"]: r for r in self.rows("people.csv")}
        self.assertEqual(len(people), 6)
        self.assertEqual((people["1"]["first_name"], people["1"]["surname"], people["1"]["birth_year"]), ("Łucja", "Żółć", "1900"))
        self.assertEqual(people["1"]["death_year"], "1980")
        self.assertEqual((people["4"]["surname"], people["4"]["birth_year"]), ("Changed", "1921"))
        self.assertEqual(people["5"]["surname"], "Found")
        self.assertEqual(people["5"]["family_name_group"], "Found")
        families = self.rows("families.csv")
        self.assertEqual(families[0]["note"], "Original chart family")
        self.assertEqual(families[-1]["children_ids"], "6")
        self.assertEqual([r["id"] for r in families], ["1", "2", "3"])
        self.assertEqual(len(self.rows("sources.csv")), 2)
        self.assertEqual(self.rows("sources.csv")[-1]["source_id"], "S2")
        self.assertTrue(any("Chart-backed" in c for c in plan["report"]["conflicts"]))
        self.assertTrue(list(self.directory.rglob("registries-*/people.csv")))
        self.validate()
        again = make_refresh_plan(self.path, self.registries)
        self.assertEqual(again["changed"], {})
        self.assertEqual(again["report"]["families_added"], [])
        self.assertEqual(again["report"]["families_removed"], [])

    def test_absent_people_are_retained_and_return_with_same_id(self):
        self.export(self.updated())
        apply_plan(make_refresh_plan(self.path, self.registries))
        self.export(self.updated(include_child=False))
        absent = make_refresh_plan(self.path, self.registries)
        self.assertEqual([r["id"] for r in absent["report"]["people_absent"]], [5])
        apply_plan(absent)
        self.assertEqual(len(self.rows("people.csv")), 6)
        self.assertIn("absent", next(r for r in self.rows("people.csv") if r["id"] == "5")["note"])
        self.assertEqual(make_refresh_plan(self.path, self.registries)["changed"], {})
        self.export(self.updated())
        returned = make_refresh_plan(self.path, self.registries)
        self.assertEqual(returned["report"]["people_added"], [])
        apply_plan(returned)
        self.assertNotIn("absent", next(r for r in self.rows("people.csv") if r["id"] == "5")["note"])
        self.validate()

    def test_local_corrections_are_not_overwritten_including_manual_blanks(self):
        people = self.rows("people.csv")
        people[3]["birth_year"] = "1922"
        people[4]["birth_year"] = ""
        self.write("people.csv", people)
        self.export(self.updated())
        apply_plan(make_refresh_plan(self.path, self.registries))
        people = self.rows("people.csv")
        self.assertEqual(people[3]["birth_year"], "1922")
        self.assertEqual(people[4]["birth_year"], "")

    def test_local_surname_does_not_acquire_the_incoming_family_group(self):
        people = self.rows("people.csv")
        people[3]["surname"] = "Family correction"
        self.write("people.csv", people)
        self.export(self.updated())
        apply_plan(make_refresh_plan(self.path, self.registries))
        self.assertEqual(self.rows("people.csv")[3]["surname"], "Family correction")
        self.assertEqual(self.rows("people.csv")[3]["family_name_group"], "Example")

    def test_unchanged_family_keeps_its_role_and_annotation_after_renumbering(self):
        families = self.rows("families.csv")
        families[1]["branch_role"] = "main_line"
        families[1]["note"] += " Family annotation retained."
        self.write("families.csv", families)
        self.export(self.updated())
        apply_plan(make_refresh_plan(self.path, self.registries))
        family = next(r for r in self.rows("families.csv") if r["mother_id"] == "1" and r["children_ids"] == "4")
        self.assertEqual(family["branch_role"], "main_line")
        self.assertIn("Family annotation retained.", family["note"])
        self.assertTrue(family["note"].startswith("S2 @F77@:"))

    def test_a_different_familysearch_id_requires_review_despite_matching_name_and_year(self):
        self.export(self.initial.replace("BBBB-BBB", "ZZZZ-ZZZ"))
        self.assertFalse(make_refresh_plan(self.path, self.registries)["report"]["ready"])
        reviewed = make_refresh_plan(self.path, self.registries, {"@I2@": 4})
        self.assertTrue(reviewed["report"]["ready"])

    def test_dated_input_can_refresh_the_explicit_existing_source(self):
        self.path = self.directory / "new-extract.ged"
        self.export(self.updated())
        plan = make_refresh_plan(self.path, self.registries, source_id="S2")
        apply_plan(plan)
        self.assertEqual(self.rows("sources.csv")[-1]["file_name"], self.path.relative_to(ROOT).as_posix())
        self.assertEqual(make_refresh_plan(self.path, self.registries)["changed"], {})

    def test_absent_snapshot_relationships_are_removed_even_without_replacements(self):
        self.export(person("@I100@", "AAAA-AAA", "Lucia", "Zolc", "1900"))
        plan = make_refresh_plan(self.path, self.registries)
        self.assertEqual(len(plan["report"]["families_removed"]), 2)
        apply_plan(plan)
        self.assertEqual(len(self.rows("families.csv")), 1)
        self.assertEqual(len(self.rows("people.csv")), 5)
        self.validate()

    def test_chart_blank_filled_by_refresh_remains_refreshable(self):
        self.export(self.updated())
        apply_plan(make_refresh_plan(self.path, self.registries))
        self.export(self.updated().replace("2 DATE 1980", "2 DATE 1981"))
        apply_plan(make_refresh_plan(self.path, self.registries))
        self.assertEqual(self.rows("people.csv")[0]["death_year"], "1981")

    def test_unknown_or_qualified_incoming_dates_clear_only_managed_year(self):
        self.export(self.updated().replace("2 DATE 1921", "2 DATE ABT 1921"))
        plan = make_refresh_plan(self.path, self.registries)
        apply_plan(plan)
        self.assertEqual(self.rows("people.csv")[3]["birth_year"], "")
        self.assertTrue(any("ABT 1921" in r["transcription"] for r in self.rows("person_source_evidence.csv")))
        self.assertTrue(plan["report"]["warnings"])

    def test_duplicate_and_conflicting_stable_id_decisions_are_rejected(self):
        self.export(self.updated().replace("FFFF-FFF", "BBBB-BBB"))
        with self.assertRaisesRegex(ValueError, "Duplicate FamilySearch"):
            make_refresh_plan(self.path, self.registries)
        self.export(self.updated())
        with self.assertRaisesRegex(ValueError, "contradicts FamilySearch"):
            make_refresh_plan(self.path, self.registries, {"@I8@": 5})

    def test_missing_ids_require_explicit_review_and_never_reuse_row_numbers(self):
        self.export(self.updated().replace("1 _FSFTID CCCC-CCC\n", ""))
        plan = make_refresh_plan(self.path, self.registries)
        self.assertFalse(plan["report"]["ready"])
        with self.assertRaisesRegex(ValueError, "Resolve"):
            apply_plan(plan)
        reviewed = make_refresh_plan(self.path, self.registries, {"@I9@": 5})
        self.assertTrue(reviewed["report"]["ready"])

    def test_locally_edited_source_family_blocks_apply(self):
        families = self.rows("families.csv")
        families[-1]["children_ids"] = "3;5"
        self.write("families.csv", families)
        self.export(self.updated())
        plan = make_refresh_plan(self.path, self.registries)
        self.assertFalse(plan["report"]["ready"])
        with self.assertRaisesRegex(ValueError, "Resolve"):
            apply_plan(plan)

    def test_shared_families_and_evidence_are_retained_and_renumbered(self):
        families = self.rows("families.csv")
        families.append(dict(id="4", father_id="2", mother_id="", children_ids="5", branch_role="main_line", note="Later chart account"))
        self.write("families.csv", families)
        evidence = self.rows("relationship_evidence.csv")
        evidence.append(dict(evidence_id="E900", family_id="4", relationship="parent-child", person_id="2", related_person_id="5", source_id="S1", confidence="confirmed"))
        self.write("relationship_evidence.csv", evidence)
        self.export(self.updated())
        plan = make_refresh_plan(self.path, self.registries)
        apply_plan(plan)
        chart_family = next(r for r in self.rows("families.csv") if r["note"] == "Later chart account")
        self.assertEqual(chart_family["id"], "2")
        link = next(r for r in self.rows("relationship_evidence.csv") if r["evidence_id"] == "E900")
        self.assertEqual(link["family_id"], chart_family["id"])
        self.assertEqual(next(r for r in self.rows("people.csv") if r["id"] == "5")["surname"], "Found")
        self.validate()

    def test_missing_snapshot_requires_verified_previous_export(self):
        archive = snapshot_path(self.path, "S2", self.initial_hash, self.registries)
        archive.unlink()
        self.export(self.updated())
        with self.assertRaisesRegex(ValueError, "Previous GEDCOM snapshot"):
            make_refresh_plan(self.path, self.registries)
        previous = self.directory / "previous.ged"
        previous.write_bytes(self.initial_bytes)
        self.assertTrue(make_refresh_plan(self.path, self.registries, previous_gedcom=previous)["report"]["ready"])

    def test_stale_input_and_archive_corruption_prevent_registry_writes(self):
        self.export(self.updated())
        plan = make_refresh_plan(self.path, self.registries)
        before = {p.name: (self.registries / p.name).read_bytes() for p in REGISTRY_PATHS}
        self.path.write_bytes(self.path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "GEDCOM changed after planning"):
            apply_plan(plan)
        self.path.write_bytes(plan["input_checks"][self.path])
        archive = next(iter(plan["archives"]))
        archive.write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "Archive already exists"):
            apply_plan(plan)
        for name, content in before.items():
            self.assertEqual((self.registries / name).read_bytes(), content)

    def test_replacement_failure_restores_all_registries(self):
        self.export(self.updated())
        plan = make_refresh_plan(self.path, self.registries)
        replace = Path.replace
        count = 0

        def fail_second(source, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated refresh failure")
            return replace(source, target)

        with patch.object(Path, "replace", fail_second), self.assertRaisesRegex(OSError, "simulated"):
            apply_plan(plan)
        for name, content in plan["originals"].items():
            self.assertEqual((self.registries / name).read_bytes(), content)
        self.assertEqual(snapshot_path(self.path, "S2", self.initial_hash, self.registries).read_bytes(), self.initial_bytes)


if __name__ == "__main__":
    unittest.main()
