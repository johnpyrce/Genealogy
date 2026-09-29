"""Build with the installed Data plugin; never install or replace its runtime."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

from scripts.lib.genealogy_data import ROOT


def resolve_builder() -> tuple[str, Path]:
    override = os.environ.get("DATA_ANALYTICS_PLUGIN")
    codex_dir = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    candidates = [Path(override)] if override else list(
        (codex_dir / "plugins/cache/openai-curated-remote/data-analytics").glob("*"))
    candidates = [p for p in candidates if (p / "scripts/data-app.mjs").is_file()]
    if not candidates:
        raise RuntimeError("Installed Data builder not found. Enable the Data plugin or set DATA_ANALYTICS_PLUGIN to its installed directory.")
    plugin = max(candidates, key=lambda p: tuple(int(n) for n in re.findall(r"\d+", p.name)))
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    node = os.environ.get("CODEX_NODE") or (str(bundled) if bundled.is_file() else shutil.which("node"))
    if not node:
        raise RuntimeError("Node unavailable. Set CODEX_NODE to the installed Node executable.")
    return node, plugin / "scripts/data-app.mjs"


def main() -> None:
    node, builder = resolve_builder()
    subprocess.run([node, str(builder), "build", "--project-dir", str(ROOT / "apps/analytics-dashboard"), "--separate-data"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
