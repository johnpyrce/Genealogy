"""Build, check, preview, and stage the repository-owned website."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

from scripts.lib.genealogy_data import ROOT

OUTPUT = ROOT / "artifacts/website"
DIST = OUTPUT / "dist"
CONFIG_PATH = ROOT / "website/site.json"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"src", "href", "poster"} and value:
                self.links.append(value)


def check_links(directory: Path) -> int:
    """Check local file targets, including embedded tools. Remote URLs are excluded."""
    missing = []
    count = 0
    for page in directory.rglob("*.html"):
        parser = Links()
        parser.feed(page.read_text(encoding="utf-8"))
        for link in parser.links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            count += 1
            path = unquote(parsed.path)
            target = (directory / path.lstrip("/") if path.startswith("/") else page.parent / path).resolve()
            if not target.is_relative_to(directory.resolve()):
                missing.append(f"{page.relative_to(directory)}: outside website: {link}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                missing.append(f"{page.relative_to(directory)}: {link}")
    if missing:
        raise ValueError("Broken internal links:\n" + "\n".join(missing))
    return count


def digest_files(paths: list[Path]) -> str:
    result = hashlib.sha256()
    for path in sorted(set(paths)):
        result.update(str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path).encode())
        result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def input_digest() -> str:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    paths = []
    for folder in ["data/registries", "data/source-material/charts", "docs", "website", "scripts", "apps/analytics-dashboard/src"]:
        paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store")
    for collection in config["collections"].values():
        directory = ROOT / collection["directory"]
        if not directory.is_dir():
            raise FileNotFoundError(f"Photo collection unavailable: {directory}")
        paths.extend(p for p in directory.iterdir() if p.is_file() and p.name != ".DS_Store")
    return digest_files(paths)


def output_digest(directory: Path) -> str:
    result = hashlib.sha256()
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        result.update(path.relative_to(directory).as_posix().encode())
        result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def build() -> None:
    # Fail before regenerating anything if dependencies or linked media are missing.
    from scripts.build_dashboard import resolve_builder
    resolve_builder()
    input_digest()
    subprocess.run(["sh", str(ROOT / "build.sh")], cwd=ROOT, check=True)
    from scripts import build_website
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = input_digest()
    with tempfile.TemporaryDirectory(prefix="building-", dir=OUTPUT) as temporary:
        destination = Path(temporary) / "dist"
        build_website.DIST = destination
        build_website.main()
        count = check_links(destination)
        if input_digest() != before:
            raise RuntimeError("Sources changed during the build. Rebuild before publishing.")
        manifest = {"project_id": build_website.CONFIG["project_id"], "input_sha256": before,
                    "output_sha256": output_digest(destination), "internal_links_checked": count}
        if DIST.exists():
            shutil.rmtree(DIST)
        shutil.move(str(destination), DIST)
        (OUTPUT / "build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Website ready: {DIST} ({count} internal links checked)")


def stage(checkout: Path) -> None:
    """Copy the verified static bundle into an opened checkout of this same Site."""
    checkout = checkout.resolve()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    hosting = json.loads((checkout / ".openai/hosting.json").read_text(encoding="utf-8"))
    if hosting.get("project_id") != config["project_id"] or hosting.get("static", {}).get("directory") != "dist":
        raise ValueError("Destination must be the opened static checkout for this exact Site.")
    if checkout == ROOT or checkout.is_relative_to(DIST) or DIST.is_relative_to(checkout):
        raise ValueError("Use a separate Sites source checkout.")
    manifest = json.loads((OUTPUT / "build.json").read_text(encoding="utf-8"))
    if manifest["input_sha256"] != input_digest() or manifest["output_sha256"] != output_digest(DIST):
        raise ValueError("The website build is stale or modified. Run ./preview_site.sh --build-only first.")
    check_links(DIST)
    target = checkout / "dist"
    if target.is_symlink():
        raise ValueError("Destination dist must not be a symlink.")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(DIST, target)
    (checkout / "genealogy-build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Staged verified website in {checkout}. Publish through the Sites workflow; access is unchanged.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="Rebuild all required artifacts and check the website")
    sub.add_parser("check", help="Check local links in the last build")
    preview = sub.add_parser("preview", help="Build and serve locally; does not publish")
    preview.add_argument("--port", type=int, default=4176)
    staging = sub.add_parser("stage", help="Stage the last verified build in an opened Site checkout")
    staging.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command in {"build", "preview"}:
            build()
        if args.command == "check":
            if not DIST.is_dir():
                raise ValueError("No website build. Run ./preview_site.sh --build-only first.")
            print(f"Checked {check_links(DIST)} internal links.")
        elif args.command == "stage":
            stage(args.checkout)
        elif args.command == "preview":
            handler = partial(SimpleHTTPRequestHandler, directory=str(DIST))
            with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
                print(f"Preview: http://127.0.0.1:{args.port}/ (Ctrl-C to stop)", flush=True)
                server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Website: {error}\n")


if __name__ == "__main__":
    main()
