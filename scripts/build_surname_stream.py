"""Build the offline surname-by-generation stream graph."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_generation_overview import build_data
from scripts.lib.genealogy_data import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts/interactive/surname_stream.html")
    args = parser.parse_args()
    payload = json.dumps(build_data(), ensure_ascii=False).replace("<", "\\u003c")
    template = (ROOT / "scripts/templates/surname_stream.html").read_text(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace("__STREAM_DATA__", payload), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
