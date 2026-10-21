"""Download a FamilySearch tree through RootsMagic and prepare a registry preview."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from zoneinfo import ZoneInfo

from scripts.import_gedcom import (
    DEFAULT_INPUT, REGISTRY_PATHS, display_report, load_decisions, make_plan,
    markdown_report, parse_gedcom,
)
from scripts.lib.genealogy_data import ROOT, REGISTRIES, load_person_source_evidence
from scripts.lib.rootsmagic_ui import AutomationError, DEFAULT_APP, RootsMagicUI, build_helper

DEFAULT_MATCHES = ROOT / "docs/imports/PyrceFamily.matches.json"
RUNS = ROOT / "artifacts/imports"
SOURCE_DIRECTORY = ROOT / "data/source-material"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_people(path: Path) -> dict[str, object]:
    return {person.xref: person for person in parse_gedcom(path) if person.tag == "INDI"}


def familysearch_index(people: dict) -> dict:
    index = {}
    for person in people.values():
        identifier = person.get("_FSFTID")
        if not identifier:
            continue
        if identifier in index:
            raise ValueError(f"Duplicate FamilySearch ID {identifier}; reconcile the GEDCOM before carrying matches forward")
        index[identifier] = person
    return index


def carry_matches(previous_gedcom: Path, previous_matches: Path, gedcom: Path) -> tuple[dict, dict, list[str], set[str]]:
    """Carry proposed identities by FamilySearch ID, never by GEDCOM row number."""
    decisions = load_decisions(previous_matches, previous_gedcom)
    previous_people = source_people(previous_gedcom)
    # Check both exports for duplicate stable IDs, including unmatched people.
    familysearch_index(previous_people)
    new_by_id = familysearch_index(source_people(gedcom))
    previous_data = json.loads(previous_matches.read_text(encoding="utf-8"))
    rationale = previous_data.get("rationale", {})
    matches, notes, warnings = {}, {}, []
    new_people = {new_by_id[person.get("_FSFTID")].xref for xref, person in previous_people.items()
                  if xref not in (decisions or {}) and person.get("_FSFTID") in new_by_id}
    for xref, registry_id in (decisions or {}).items():
        if xref not in previous_people:
            raise ValueError(f"Previous match {xref} is absent from its GEDCOM")
        person = previous_people[xref]
        identifier = person.get("_FSFTID")
        if not identifier:
            warnings.append(f"Previous match {xref} has no FamilySearch ID; it was not carried forward.")
            continue
        if identifier not in new_by_id:
            warnings.append(f"Previous match {xref} ({identifier}) is absent from this download.")
            continue
        new_xref = new_by_id[identifier].xref
        matches[new_xref] = registry_id
        notes[new_xref] = (rationale.get(xref, "Previously proposed existing-person match.")
                          + f" Carried forward by FamilySearch ID {identifier}; review this proposal before applying.")
    return matches, notes, warnings, new_people


def registry_familysearch_ids() -> dict[str, int]:
    """Read stable identities already recorded in verbatim import evidence."""
    result = {}
    for row in load_person_source_evidence():
        if not row["location"].startswith("GEDCOM "):
            continue
        for identifier in re.findall(r"^1 _FSFTID ([A-Z0-9]{4}-[A-Z0-9]{3})\s*$", row["transcription"], flags=re.M):
            person_id = int(row["person_id"])
            if identifier in result and result[identifier] != person_id:
                raise ValueError(f"FamilySearch ID {identifier} is linked to multiple registry people; reconcile before fetching matches")
            result[identifier] = person_id
    return result


def prepare_preview(gedcom: Path, directory: Path, previous_gedcom: Path | None = None,
                    previous_matches: Path | None = None) -> dict:
    """Discover additional candidates, and save a sparse proposal and full report."""
    matches, rationale, warnings, new_people = {}, {}, [], set()
    if (previous_gedcom is None) != (previous_matches is None):
        raise ValueError("Supply both previous GEDCOM and previous matches, or neither")
    if previous_gedcom is not None:
        matches, rationale, warnings, new_people = carry_matches(previous_gedcom, previous_matches, gedcom)
    known_ids = registry_familysearch_ids()
    for identifier, person in familysearch_index(source_people(gedcom)).items():
        if identifier not in known_ids:
            continue
        person_id = known_ids[identifier]
        if person.xref in matches and matches[person.xref] != person_id:
            raise ValueError(f"Previous match for {identifier} contradicts existing registry provenance")
        matches[person.xref] = person_id
        rationale[person.xref] = f"Existing GEDCOM person evidence links FamilySearch ID {identifier} to registry person {person_id}."
        new_people.discard(person.xref)
    plan = make_plan(gedcom, match_overrides=matches, new_people=new_people)
    report = plan["report"]
    report["mode"] = "preview"
    report["warnings"].extend(warnings)
    for row in report["people_matched"]:
        matches[row["gedcom_id"]] = row["id"]
        rationale.setdefault(row["gedcom_id"], "Proposed by the importer: " + row["reason"] + ". Review before applying.")
    directory.mkdir(parents=True, exist_ok=True)
    match_path = directory / "matches.json"
    write_json(match_path, dict(
        description="Proposed existing-person matches. Review before applying; people omitted from the reviewed match file are added as new people.",
        gedcom_sha256=digest(gedcom), rationale=rationale, people=matches))
    write_json(directory / "preview.json", report)
    (directory / "preview.md").write_text(markdown_report(report), encoding="utf-8")
    display_report(report)
    print(f"\nProposed matches: {match_path}")
    print(f"Preview: {directory / 'preview.md'}")
    if not report["ready"]:
        print("Review unresolved candidates before using matches.json; omitted candidates become new people only when you supply that reviewed file.")
    return report


def validate_export(gedcom: Path, person: str, expected: dict) -> dict:
    records = parse_gedcom(gedcom)
    people = [record for record in records if record.tag == "INDI"]
    families = [record for record in records if record.tag == "FAM"]
    if len(people) != expected["downloaded_people"] or len(families) != expected["downloaded_families"]:
        raise ValueError("GEDCOM counts do not match the completed RootsMagic download")
    if not any(record.get("_FSFTID") == person for record in people):
        raise ValueError("The GEDCOM does not contain the requested FamilySearch person ID; verify RootsMagic's extra-details export option")
    familysearch_index({record.xref: record for record in people})
    return dict(people=len(people), families=len(families), sha256=digest(gedcom))


def reserve_run(person: str, output_directory: Path, now: datetime | None = None) -> dict:
    """Reserve a unique run directory; existing GEDCOM/database files are refused."""
    output_directory = output_directory.resolve()
    if not output_directory.is_relative_to(ROOT) or output_directory.is_relative_to(REGISTRIES):
        raise ValueError("GEDCOM output must be inside the repository and outside the registries")
    timestamp = (now or datetime.now(ZoneInfo("America/Chicago"))).strftime("%Y-%m-%d_%H%M%S_%f")
    name = f"FamilySearch-{person}-{timestamp}"
    directory = RUNS / name
    gedcom = output_directory / (name + ".ged")
    database = directory / (name + ".rmtree")
    if gedcom.exists() or directory.exists():
        raise ValueError("This run already exists; choose a new run instead of overwriting files")
    output_directory.mkdir(parents=True, exist_ok=True)
    directory.mkdir(parents=True, exist_ok=False)
    return dict(directory=directory, gedcom=gedcom, database=database)


@contextmanager
def fetch_lock():
    import fcntl
    RUNS.mkdir(parents=True, exist_ok=True)
    with (RUNS / ".fetch.lock").open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise AutomationError("Another genealogy fetch is already running in this repository") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def fetch(args: argparse.Namespace, driver_factory=RootsMagicUI) -> int:
    if driver_factory is RootsMagicUI and sys.platform != "darwin":
        raise AutomationError("RootsMagic desktop download requires macOS 14 or newer")
    if args.no_previous_matches and (args.previous_gedcom or args.previous_matches):
        raise ValueError("Do not combine --no-previous-matches with previous-source options")
    previous_gedcom = args.previous_gedcom.resolve() if args.previous_gedcom else None
    previous_matches = args.previous_matches.resolve() if args.previous_matches else None
    if args.no_previous_matches:
        previous_gedcom = previous_matches = None
    elif not args.previous_gedcom and not args.previous_matches:
        if DEFAULT_INPUT.is_file() and DEFAULT_MATCHES.is_file():
            previous_gedcom, previous_matches = DEFAULT_INPUT, DEFAULT_MATCHES
    if (previous_gedcom is None) != (previous_matches is None):
        raise ValueError("Supply both --previous-gedcom and --previous-matches")
    if previous_gedcom is not None:
        load_decisions(previous_matches, previous_gedcom)
    before = {path: digest(path) for path in REGISTRY_PATHS}
    with fetch_lock():
        job = reserve_run(args.person, args.output_directory)
        directory, gedcom, database = job["directory"], job["gedcom"], job["database"]
        manifest = dict(status="starting", starting_familysearch_id=args.person,
                        ancestor_generations=args.ancestors, descendant_generations=args.descendants,
                        gedcom=str(gedcom.relative_to(ROOT)), database=str(database.relative_to(ROOT)),
                        registry_import_applied=False, registry_sha256_before={str(path.relative_to(ROOT)): value for path, value in before.items()})
        manifest_path = directory / "download.json"
        write_json(manifest_path, manifest)
        print(f"Run directory: {directory}", flush=True)
        try:
            driver = driver_factory(directory / "ui", args.app)
            metadata = driver.fetch(args.person, args.ancestors, args.descendants, database, gedcom, timeout=args.timeout)
            manifest.update(metadata, status="downloaded", **validate_export(gedcom, args.person, metadata))
            write_json(manifest_path, manifest)
            report = prepare_preview(gedcom, directory, previous_gedcom, previous_matches)
            if any(digest(path) != value for path, value in before.items()):
                raise ValueError("Registries changed during the download; regenerate the preview against the current registries")
            manifest.update(status="preview_ready" if report["ready"] else "needs_review",
                            people_matched=len(report["people_matched"]), people_added=len(report["people_added"]),
                            families_added=len(report["families_added"]), matches=str((directory / "matches.json").relative_to(ROOT)))
            write_json(manifest_path, manifest)
            print("\nAfter reviewing the proposed matches, rerun the preview with:")
            print(shlex.join(["./genealogy.sh", "preview", str(gedcom.relative_to(ROOT)), "--matches", str((directory / "matches.json").relative_to(ROOT))]))
            return 0 if report["ready"] else 2
        except (Exception, KeyboardInterrupt) as error:
            manifest.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed", error=str(error))
            write_json(manifest_path, manifest)
            print(f"Fetch stopped. Run details and last UI observation: {directory}", file=sys.stderr)
            raise


def preview(args: argparse.Namespace) -> int:
    if args.matches:
        plan = make_plan(args.gedcom, decisions=load_decisions(args.matches, args.gedcom))
        report = plan["report"]
        report["mode"] = "preview"
        display_report(report)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            if args.report.suffix == ".md":
                args.report.write_text(markdown_report(report), encoding="utf-8")
            else:
                write_json(args.report, report)
        return 0 if report["ready"] else 2
    directory = args.directory or RUNS / (args.gedcom.stem + "-review")
    report = prepare_preview(args.gedcom, directory, args.previous_gedcom, args.previous_matches)
    return 0 if report["ready"] else 2


def doctor(args: argparse.Namespace) -> int:
    helper = build_helper()
    result = subprocess.run([str(helper)], input=json.dumps(dict(action="check", app=str(args.app))),
                            capture_output=True, text=True, timeout=15, check=True)
    state = json.loads(result.stdout)
    print(f"Native helper: {helper}")
    print(f"RootsMagic: {args.app} ({state['version']})")
    print(f"Application installed: {state['app_exists']}")
    print(f"Accessibility permission: {state['accessibility']}")
    print(f"Screen Recording permission: {state['screen_recording']}")
    ready = state["app_exists"] and state["accessibility"] and state["screen_recording"] and str(state["version"]).startswith("12.")
    if not ready:
        print("Use RootsMagic 12 in English on macOS 14+. Enable Accessibility and Screen Recording for your terminal in System Settings → Privacy & Security, then restart that terminal. No permissions were changed.")
    return 0 if ready else 1


def person_id(value: str) -> str:
    value = value.upper()
    if not re.fullmatch(r"[A-Z0-9]{4}-[A-Z0-9]{3}", value):
        raise argparse.ArgumentTypeError("Use a FamilySearch person ID such as G4ZN-5FR")
    return value


def generations(value: str) -> int:
    number = int(value)
    if not 0 <= number <= 100:
        raise argparse.ArgumentTypeError("Generation count must be between 0 and 100")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    get = sub.add_parser("fetch", help="Download through RootsMagic and save a proposed import preview")
    get.add_argument("--person", type=person_id, default="G4ZN-5FR")
    get.add_argument("--ancestors", type=generations, default=10)
    get.add_argument("--descendants", type=generations, default=4)
    get.add_argument("--app", type=Path, default=DEFAULT_APP)
    get.add_argument("--timeout", type=int, default=600, help="Maximum seconds for sign-in and download separately")
    get.add_argument("--output-directory", type=Path, default=SOURCE_DIRECTORY)
    get.add_argument("--previous-gedcom", type=Path)
    get.add_argument("--previous-matches", type=Path)
    get.add_argument("--no-previous-matches", action="store_true", help="Discover overlaps without carrying forward previous proposals")
    inspect = sub.add_parser("preview", help="Preview an existing GEDCOM without using the desktop")
    inspect.add_argument("gedcom", type=Path)
    inspect.add_argument("--matches", type=Path, help="Reviewed sparse matches; omitted people are additions")
    inspect.add_argument("--report", type=Path, help="Save reviewed preview as .md or .json")
    inspect.add_argument("--directory", type=Path, help="Directory for newly proposed matches and reports")
    inspect.add_argument("--previous-gedcom", type=Path)
    inspect.add_argument("--previous-matches", type=Path)
    check = sub.add_parser("doctor", help="Build the local helper and check macOS permissions; no UI input")
    check.add_argument("--app", type=Path, default=DEFAULT_APP)
    if len(sys.argv) == 1:
        parser.print_help()
        return
    args = parser.parse_args()
    if args.command == "fetch" and args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        code = {"fetch": fetch, "preview": preview, "doctor": doctor}[args.command](args)
    except KeyboardInterrupt:
        parser.exit(130, "Stopped by user. Existing source files and registries were preserved.\n")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Genealogy command failed: {error}\n")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
