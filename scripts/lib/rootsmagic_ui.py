"""macOS RootsMagic 12 driver for the command-line FamilySearch workflow.

The native helper reads the target window with ScreenCaptureKit/Vision. Native
save dialogs use accessibility identifiers; custom RootsMagic controls use OCR.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
from typing import Callable

from scripts.lib.genealogy_data import ROOT

SOURCE = ROOT / "scripts/native/rootsmagic_ui.swift"
HELPER = ROOT / "artifacts/tools/rootsmagic-ui"
DEFAULT_APP = Path("/Applications/RootsMagic 12.app")


class AutomationError(RuntimeError):
    """The expected UI could not be recognized or safely operated."""


def report_progress(message: str) -> None:
    print(message, flush=True)


def normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def build_helper() -> Path:
    if platform.system() != "Darwin":
        raise AutomationError("RootsMagic desktop download requires macOS 14 or newer")
    if not shutil.which("swiftc"):
        raise AutomationError("Apple Command Line Tools are required. Install them with xcode-select --install, then retry.")
    if not HELPER.exists() or HELPER.stat().st_mtime < SOURCE.stat().st_mtime:
        HELPER.parent.mkdir(parents=True, exist_ok=True)
        destination = HELPER.with_suffix(".building")
        result = subprocess.run([
            "swiftc", "-parse-as-library", "-target", f"{platform.machine()}-apple-macos14.0",
            str(SOURCE), "-o", str(destination), "-framework", "AppKit", "-framework",
            "ApplicationServices", "-framework", "ScreenCaptureKit", "-framework", "Vision",
        ], capture_output=True, text=True, timeout=180, check=False)
        if result.returncode:
            raise AutomationError("Cannot build the macOS helper:\n" + result.stderr)
        destination.replace(HELPER)
    return HELPER


@dataclass
class Observation:
    data: dict

    @property
    def text(self) -> str:
        return "\n".join([self.data.get("window_title", "")] + [item["text"] for item in self.data["labels"]])

    def contains(self, text: str) -> bool:
        return normalized_label(text) in normalized_label(self.text)

    def field(self, identifier: str) -> bool:
        return any(item["identifier"] == identifier for item in self.data.get("fields", []))

    def labels(self, text: str, left_of: float | None = None) -> list[dict]:
        return [item for item in self.data["labels"]
                if normalized_label(item["text"]) == normalized_label(text)
                and item.get("confidence", 1) >= .55
                and (left_of is None or item["x"] + item["width"] / 2 < left_of)]

    def unique(self, text: str, left_of: float | None = None) -> dict:
        matches = self.labels(text, left_of)
        if len(matches) != 1:
            raise AutomationError(f"Expected one visible {text!r} control; found {len(matches)}")
        return matches[0]


class RootsMagicUI:
    def __init__(self, directory: Path, app: Path = DEFAULT_APP,
                 progress: Callable[[str], None] = report_progress):
        self.directory = directory
        self.app = app
        self.helper = build_helper()
        self.progress = progress
        self.last: Observation | None = None
        self.phase = "starting"

    def command(self, action: str, **arguments) -> dict:
        result = subprocess.run([str(self.helper)], input=json.dumps(dict(action=action, app=str(self.app), **arguments)),
                                capture_output=True, text=True, timeout=45, check=False)
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise AutomationError(f"macOS helper {action} failed: {result.stderr.strip() or result.stdout.strip()}") from error
        if result.returncode or "error" in response:
            raise AutomationError(response.get("error", result.stderr.strip()))
        return response

    def observe(self) -> Observation:
        self.directory.mkdir(parents=True, exist_ok=True)
        for attempt in range(5):
            try:
                state = Observation(self.command("snapshot", screenshot=str(self.directory / "latest.png")))
                break
            except AutomationError as error:
                transient = ("Window geometry", "Cannot identify the RootsMagic window",
                             "Cannot capture the focused RootsMagic window", "SCStreamErrorDomain")
                if attempt == 4 or not any(message in str(error) for message in transient):
                    raise
                time.sleep(.3)
        self.last = state
        (self.directory / "latest.json").write_text(json.dumps(state.data, indent=2) + "\n", encoding="utf-8")
        if state.contains("Replace") and state.contains("already exists"):
            raise AutomationError("RootsMagic is asking to replace a file; existing files will not be overwritten")
        return state

    def wait(self, predicate: Callable[[Observation], bool], description: str,
             timeout: float = 30, interval: float = .5) -> Observation:
        deadline = time.monotonic() + timeout
        while True:
            state = self.observe()
            if predicate(state):
                return state
            if time.monotonic() >= deadline:
                raise AutomationError(f"Timed out waiting for {description}. Last window: {state.data.get('window_title')}")
            time.sleep(interval)

    def wait_text(self, text: str, timeout: float = 30) -> Observation:
        return self.wait(lambda state: state.contains(text), text, timeout)

    def click(self, state: Observation, x: float, y: float) -> None:
        self.command("click", window_id=state.data["window_id"], x=x, y=y)

    def click_text(self, text: str, left_of: float | None = None) -> None:
        state = self.observe()
        label = state.unique(text, left_of)
        self.click(state, label["x"] + label["width"] / 2, label["y"] + label["height"] / 2)

    def replace_text(self, text: str) -> None:
        self.command("key", key="select_all")
        self.command("type", text=text)

    def stage(self, phase: str) -> None:
        self.phase = phase
        self.progress(phase)
        if self.last and (self.directory / "latest.png").exists():
            shutil.copyfile(self.directory / "latest.png", self.directory / (re.sub(r"[^a-z0-9]+", "-", phase.lower()).strip("-") + ".png"))

    def ensure_sidebar(self) -> None:
        state = self.observe()
        def expanded(observed: Observation) -> bool:
            # A collapsed page also has a small "File" context caption at y=123.
            return any(140 < label["y"] < 175 for label in observed.labels("File", left_of=150))

        if expanded(state):
            return
        bounds = state.data["bounds"]
        if bounds["width"] < 800 or bounds["height"] < 600 or not state.data["window_title"].startswith("RootsMagic 12"):
            raise AutomationError("Cannot expand the sidebar outside RootsMagic's main window")
        # The collapsed sidebar's expand chevron is an unlabeled custom control.
        self.click(state, 22, 79)
        self.wait(expanded, "expanded RootsMagic sidebar")

    def prepare_start(self, timeout: int) -> None:
        state = self.observe()
        if state.data["window_title"] == "FamilySearch Central":
            self.click_text("Close")
            self.wait(lambda observed: observed.data["window_title"].startswith("RootsMagic 12"),
                      "FamilySearch Central to close")
            state = self.observe()
        if state.contains("Download from an Online Tree"):
            return
        self.ensure_sidebar()
        self.click_text("File", left_of=150)
        self.wait_text("Create a New RootsMagic file")
        state = self.observe()
        if state.contains("Close this file"):
            self.stage("Closing the current tree; complete any RootsMagic backup prompt if shown")
            self.click_text("Close this file")
            self.wait(lambda observed: observed.data["window_title"] == "RootsMagic 12",
                      "current tree to close (finish any backup prompt in RootsMagic)", timeout, interval=2)
        self.ensure_sidebar()
        self.click_text("Home", left_of=150)
        self.wait_text("Download from an Online Tree")

    def save_dialog(self, destination: Path) -> None:
        if destination.exists():
            raise AutomationError(f"Output already exists: {destination}")
        self.wait(lambda state: state.field("saveAsNameTextField"), "native save dialog")
        self.command("set", identifier="saveAsNameTextField", value=destination.stem)
        self.command("key", key="go_to_folder")
        self.wait(lambda state: state.field("PathTextField"), "Go to Folder field")
        self.command("set", identifier="PathTextField", value=str(destination.parent))
        self.command("key", key="return")
        self.wait(lambda state: state.field("saveAsNameTextField") and not state.field("PathTextField"), "destination folder")
        self.command("press", identifier="OKButton")

    def enable_familysearch(self) -> None:
        state = self.observe()
        label = state.unique("FamilySearch Family Tree Support")
        row = [item for item in state.data["labels"] if normalized_label(item["text"]) in {"on", "off"}
               and item["x"] > label["x"] + label["width"]
               and abs((item["y"] + item["height"] / 2) - (label["y"] + label["height"] / 2)) < 12]
        if len(row) != 1:
            raise AutomationError("Cannot determine the new database's FamilySearch support setting")
        if normalized_label(row[0]["text"]) == "off":
            # RootsMagic's switch is immediately to the left of its On/Off label.
            self.click(state, row[0]["x"] - 30, label["y"] + label["height"] / 2)
            updated = self.observe()
            if not any(normalized_label(item["text"]) == "on" and abs(item["y"] - row[0]["y"]) < 12 for item in updated.data["labels"]):
                raise AutomationError("FamilySearch support did not turn on")

    def set_generations(self, name: str, value: int) -> None:
        state = self.observe()
        label = state.unique(name)
        # This custom spinner has an editable value 40 points before its label.
        self.click(state, label["x"] - 40, label["y"] + label["height"] / 2)
        self.replace_text(str(value))
        self.command("key", key="tab")
        updated = self.observe()
        candidates = [item for item in updated.data["labels"]
                      if label["x"] - 95 < item["x"] < label["x"]
                      and abs(item["y"] - label["y"]) < 12
                      and normalized_label(item["text"]) == str(value)]
        if len(candidates) != 1:
            raise AutomationError(f"Could not verify {name.lower()} generation count {value}")

    def fetch(self, person: str, ancestors: int, descendants: int, database: Path,
              gedcom: Path, timeout: int = 600) -> dict:
        permissions = self.command("check")
        if not permissions["app_exists"]:
            raise AutomationError(f"RootsMagic is not installed at {self.app}")
        if not permissions["accessibility"] or not permissions["screen_recording"]:
            raise AutomationError("Enable Accessibility and Screen Recording for your terminal in System Settings → Privacy & Security, restart the terminal, and retry ./genealogy doctor. Permissions are not changed automatically.")
        if not str(permissions["version"]).startswith("12."):
            raise AutomationError("This UI driver supports RootsMagic 12 in English")
        self.stage("Opening RootsMagic")
        self.command("launch")
        self.prepare_start(timeout)
        self.click_text("Download from an Online Tree")
        self.wait_text("Which website do you want to download from")
        self.click_text("Download from FamilySearch Family Tree")
        self.wait_text("Create a New RootsMagic file")
        self.click_text("Browse for Another Folder")
        self.save_dialog(database)
        self.wait_text("New File Options")
        self.enable_familysearch()
        self.click_text("OK")
        self.stage("Waiting for FamilySearch sign-in; complete it in your browser if requested")
        self.wait(lambda state: state.contains("FamilySearch ID"), "FamilySearch sign-in and import settings", timeout, interval=2)
        self.set_generations("Ancestors", ancestors)
        self.set_generations("Descendants", descendants)
        self.click_text("FamilySearch ID")
        self.replace_text(person)
        state = self.observe()
        if not state.contains(person):
            raise AutomationError("Could not verify the FamilySearch starting-person ID")
        self.click_text("Import")
        self.stage("Downloading FamilySearch tree")
        last_progress = ""

        def complete(state: Observation) -> bool:
            nonlocal last_progress
            counts = re.findall(r"(?:People|Families)\s*:\s*\d+", state.text, flags=re.I)
            progress = "; ".join(counts)
            if progress and progress != last_progress:
                self.progress(progress)
                last_progress = progress
            return state.contains("Import Complete")

        complete_state = self.wait(complete, "FamilySearch download completion", timeout, interval=2)
        counts = {key.lower(): int(value) for key, value in re.findall(r"(People|Families)\s*:\s*(\d+)", complete_state.text, flags=re.I)}
        if set(counts) != {"people", "families"} or not counts["people"]:
            raise AutomationError("Cannot verify the completed download's people/family counts")
        self.click_text("Done")
        self.wait_text(database.stem)
        self.stage("Exporting GEDCOM")
        self.ensure_sidebar()
        self.click_text("File", left_of=150)
        self.wait_text("Export Data")
        self.click_text("Export Data")
        self.wait_text("GEDCOM File")
        self.click_text("GEDCOM File")
        self.wait_text("Browse for Another Folder")
        self.click_text("Browse for Another Folder")
        self.save_dialog(gedcom)
        self.wait_text("Gedcom Export Options")
        state = self.observe()
        if not state.labels("Everyone"):
            raise AutomationError("GEDCOM export must be set to Everyone; select it in RootsMagic before retrying")
        self.click_text("OK")
        # The export dialog disappears while its AX window is being destroyed.
        # Verify the written file instead of requiring a screenshot of that race.
        deadline, previous = time.monotonic() + timeout, None
        while True:
            if gedcom.is_file():
                stat = gedcom.stat()
                current = (stat.st_size, stat.st_mtime_ns)
                if current == previous and current[0] > 0:
                    break
                previous = current
            if time.monotonic() >= deadline:
                self.observe()
                raise AutomationError("Timed out waiting for the GEDCOM export file")
            time.sleep(.5)
        return dict(version=permissions["version"], downloaded_people=counts["people"], downloaded_families=counts["families"])
