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
    # Data 1.2 keeps its HTML tooling below output_formats/html; older
    # versions expose the same CLI at the plugin root. Overrides may name either.
    builders = []
    for plugin in candidates:
        for relative in ("output_formats/html/scripts/data-app.mjs", "scripts/data-app.mjs"):
            builder = plugin / relative
            if builder.is_file():
                builders.append((plugin, builder))
                break
    if not builders:
        raise RuntimeError("Installed Data builder not found. Enable the Data plugin or set DATA_ANALYTICS_PLUGIN to its installed directory.")
    _, builder = max(builders, key=lambda pair: tuple(int(n) for n in re.findall(r"\d+", pair[0].name)))
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    node = os.environ.get("CODEX_NODE") or (str(bundled) if bundled.is_file() else shutil.which("node"))
    if not node:
        raise RuntimeError("Node unavailable. Set CODEX_NODE to the installed Node executable.")
    return node, builder


def main() -> None:
    node, builder = resolve_builder()
    # The report's decade-axis label stride requires the copied source renderer;
    # the installed prebuilt renderer does not implement xTickStride.
    subprocess.run([node, str(builder), "build", "--project-dir", str(ROOT / "apps/analytics-dashboard"), "--source"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
