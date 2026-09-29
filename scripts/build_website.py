#!/usr/bin/env python3
"""Build the static Muszyna Family Archive site from repository sources."""

from __future__ import annotations

import html
import json
import re
import shutil
import hashlib
import unicodedata
from string import Template
from PIL import Image, ImageOps
from pathlib import Path
from urllib.parse import quote


from scripts.lib.genealogy_data import ROOT, load_sources

CONFIG = json.loads((ROOT / "website/site.json").read_text(encoding="utf-8"))
DIST = ROOT / "artifacts/website/dist"
NAV = CONFIG["navigation"]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = DIST / path
    if not target.resolve().is_relative_to(DIST.resolve()):
        raise ValueError(f"Website output must stay inside dist: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def inline(text: str, link_map: dict[str, str] | None = None) -> str:
    link_map = link_map or {}
    tokens: list[str] = []

    def hold(value: str) -> str:
        tokens.append(value)
        return f"\x00{len(tokens) - 1}\x00"

    def image(match: re.Match[str]) -> str:
        alt, url = match.group(1), match.group(2).strip("<>")
        url = link_map.get(url, url)
        return hold(f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(alt, quote=True)}">')

    def link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2).strip("<>")
        url = link_map.get(url, url)
        return hold(f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>')

    text = re.sub(r"!\[([^]]*)\]\(([^)]+)\)", image, text)
    text = re.sub(r"\[([^]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"`([^`]+)`", lambda m: hold(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    for index, token in enumerate(tokens):
        text = text.replace(f"\x00{index}\x00", token)
    return text


def markdown(text: str, link_map: dict[str, str] | None = None) -> tuple[str, str]:
    """Render the small Markdown subset used by the repository documents."""
    lines = text.splitlines()
    out: list[str] = []
    title = ""
    i = 0
    in_code = False
    code_lines: list[str] = []

    def is_special(line: str) -> bool:
        return (
            not line.strip()
            or line.startswith("#")
            or line.startswith("- ")
            or re.match(r"^\d+\. ", line) is not None
            or line.startswith(">")
            or line.startswith("```")
            or line.lstrip().startswith(("<a ", "<img "))
            or (line.startswith("|") and line.endswith("|"))
            or re.match(r"^!\[[^]]*\]\([^)]+\)$", line.strip()) is not None
        )

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            if in_code:
                out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            label = heading.group(2)
            if level == 1 and not title:
                title = re.sub(r"[*`]", "", label)
            out.append(f"<h{level}>{inline(label, link_map)}</h{level}>")
            i += 1
            continue
        if line.startswith("|") and line.endswith("|") and i + 1 < len(lines):
            separator = lines[i + 1]
            if re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", separator):
                headers = [cell.strip() for cell in line.strip("|").split("|")]
                i += 2
                rows: list[list[str]] = []
                while i < len(lines) and lines[i].startswith("|") and lines[i].endswith("|"):
                    rows.append([cell.strip() for cell in lines[i].strip("|").split("|")])
                    i += 1
                out.append('<div class="table-scroll"><table><thead><tr>')
                out.extend(f"<th>{inline(cell, link_map)}</th>" for cell in headers)
                out.append("</tr></thead><tbody>")
                for row in rows:
                    out.append("<tr>")
                    out.extend(f"<td>{inline(cell, link_map)}</td>" for cell in row)
                    out.append("</tr>")
                out.append("</tbody></table></div>")
                continue
        if line.startswith("- "):
            items: list[str] = []
            while i < len(lines) and lines[i].startswith("- "):
                item = lines[i][2:].strip()
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and not is_special(lines[i]):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append("<ul>" + "".join(f"<li>{inline(item, link_map)}</li>" for item in items) + "</ul>")
            continue
        if re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                item = re.sub(r"^\d+\. ", "", lines[i]).strip()
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and not is_special(lines[i]):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append("<ol>" + "".join(f"<li>{inline(item, link_map)}</li>" for item in items) + "</ol>")
            continue
        if line.startswith(">"):
            quoted: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                quoted.append(lines[i].lstrip("> "))
                i += 1
            out.append(f"<blockquote>{inline(' '.join(quoted), link_map)}</blockquote>")
            continue
        if line.lstrip().startswith(("<a ", "<img ")):
            raw: list[str] = []
            while i < len(lines) and lines[i].strip():
                raw.append(lines[i])
                i += 1
            out.append("\n".join(raw))
            continue
        if re.match(r"^!\[[^]]*\]\([^)]+\)$", line.strip()):
            out.append(f'<figure class="document-image">{inline(line.strip(), link_map)}</figure>')
            i += 1
            continue
        paragraph = [line.strip()]
        i += 1
        while i < len(lines) and not is_special(lines[i]):
            paragraph.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(paragraph), link_map)}</p>")

    return title, "\n".join(out)


def header() -> str:
    links = "".join(f'<a href="{href}">{label}</a>' for href, label in NAV)
    return f'''<a class="skip-link" href="#content">Skip to content</a>
<header class="site-header">
  <a class="brand" href="/">Muszyna Family Archive</a>
  <button class="menu-button" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
  <nav id="site-nav" class="site-nav" aria-label="Primary navigation">{links}</nav>
</header>'''


def footer() -> str:
    return '''<footer class="site-footer"><span>Combined Muszyna Genealogy</span><a href="mailto:rekarpyrce@gmail.com">Comments</a></footer>'''


def page(title: str, body: str, description: str = "Combined Muszyna Genealogy") -> str:
    template = Template((ROOT / "website/templates/page.html").read_text(encoding="utf-8"))
    return template.substitute(description=html.escape(description, quote=True),
                               title=html.escape(title), header=header(), body=body, footer=footer())


def doc_page(source: str, output: str, *, link_map: dict[str, str] | None = None) -> None:
    title, body = markdown(read(source), link_map)
    write(output, page(title, f'<article class="document">{body}</article>', title))


def section_card(href: str, label: str) -> str:
    """Render navigation cards with a consistent, destination-led color cue."""
    tones = {
        "/sources/": "archive",
        "/names/": "lineage",
        "/analytics/": "insight",
        "/tree/": "tree",
        "/download/": "record",
        "/stories/": "story",
        "/photos/": "memory",
        "/america/": "passage",
    }
    tone = next((name for prefix, name in tones.items() if href.startswith(prefix)), "default")
    return (
        f'<a class="section-card section-card--{tone}" href="{href}">'
        f"{html.escape(label)}</a>"
    )


def card_index(title: str, links: list[tuple[str, str]], output: str) -> None:
    cards = "".join(section_card(href, label) for href, label in links)
    body = f'<section class="page-title"><h1>{html.escape(title)}</h1></section><nav class="section-grid" aria-label="{html.escape(title)}">{cards}</nav>'
    write(output, page(title, body, title))


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def build_home() -> None:
    title, intro = markdown(read(CONFIG["documents"]["home"]["source"]))
    sections = [
        ("/sources/", "Sources"),
        ("/names/", "Names"),
        ("/analytics/", "Genealogy analytics"),
        ("/tree/", "Interactive family tree"),
        ("/download/", "Download"),
        ("/stories/", "Stories"),
        ("/photos/", "Pictures from Muszyna"),
        ("/america/", "Joseph and Sophie in America"),
    ]
    links = "".join(section_card(href, label) for href, label in sections)
    body = f'<article class="document intro">{intro}</article><section class="index"><h2>Sections</h2><nav class="section-grid">{links}</nav></section>'
    write(CONFIG["documents"]["home"]["output"], page(title, body, title))


def build_sources() -> None:
    title, report = markdown(read(CONFIG["documents"]["sources"]["source"]))
    rows = load_sources().values()
    cards = []
    for row in rows:
        source = ROOT / row["file_name"]
        copy_file(source, DIST / "assets/charts" / source.name)
        url = "/assets/charts/" + quote(source.name)
        cards.append(f'''<figure class="media-card"><a href="{url}"><img src="{url}" alt="{html.escape(row['display_name'], quote=True)}" loading="lazy"></a><figcaption>{html.escape(row['source_id'])} · {html.escape(row['display_name'])}</figcaption></figure>''')
    heading = "<h2>Original chart images</h2>"
    if heading not in report:
        raise ValueError("The transcription must include an 'Original chart images' subheading.")
    images = f'<div class="media-grid">{"".join(cards)}</div>'
    report = report.replace(heading, heading + images, 1)
    body = f'<article class="document">{report}</article>'
    write(CONFIG["documents"]["sources"]["output"], page(title, body, title))


def build_names() -> None:
    card_index("Names", [
        ("/names/goscinski/", "Gościński"),
        ("/names/pyrc/", "Pyrć"),
        ("/names/pyrce/", "Pyrce"),
    ], "names/index.html")
    copy_file(
        ROOT / CONFIG["coat_of_arms"],
        DIST / "names/goscinski/doliwa_coat_of_arms.svg",
    )
    doc_page(CONFIG["documents"]["goscinski"]["source"], CONFIG["documents"]["goscinski"]["output"])
    doc_page(CONFIG["documents"]["pyrc"]["source"], CONFIG["documents"]["pyrc"]["output"])
    doc_page(CONFIG["documents"]["pyrce"]["source"], CONFIG["documents"]["pyrce"]["output"], link_map=america_link_map())


def build_tree() -> None:
    title, introduction = markdown(read(CONFIG["documents"]["tree"]["source"]))
    links = [
        ("/tree/viewer/", "Family-tree viewer"),
        ("/tree/graph/", "Relationship graph"),
        ("/tree/text/", "Text family tree"),
    ]
    cards = "".join(section_card(href, label) for href, label in links)
    body = (
        f'<article class="document">{introduction}</article>'
        f'<nav class="section-grid" aria-label="{html.escape(title)}">{cards}</nav>'
    )
    write(CONFIG["documents"]["tree"]["output"], page(title, body, title))
    artifacts = ROOT / "artifacts/interactive"
    viewer_dir = DIST / "tree/viewer/app"
    graph_dir = DIST / "tree/graph/app"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)
    for name in ["family_tree.html", "family_tree_help.html", "family_chart_elements.png"]:
        copy_file(artifacts / name, viewer_dir / name)
    for name in ["genealogy_relationship_graph.html", "genealogy_relationship_graph_help.html", "cytoscape_genealogy_graph_elements.png"]:
        copy_file(artifacts / name, graph_dir / name)
    for route, label, src in [
        ("tree/viewer/index.html", "Family-tree viewer", "/tree/viewer/app/family_tree.html"),
        ("tree/graph/index.html", "Relationship graph", "/tree/graph/app/genealogy_relationship_graph.html"),
    ]:
        body = f'<section class="tool-page"><h1>{label}</h1><iframe src="{src}" title="{label}"></iframe></section>'
        write(route, page(label, body, label))
    tree_document = read(CONFIG["documents"]["text_tree"]["source"])
    _, separator, remainder = tree_document.partition("```text\n")
    tree_text, closing, _ = remainder.partition("\n```")
    if not separator or not closing:
        raise ValueError("The generated text tree must contain a fenced text block.")
    write("tree/text/family_tree.txt", tree_text + "\n")
    text_title, text_body = markdown(tree_document)
    download_link = (
        '<p><a href="/tree/text/family_tree.txt" download="family_tree.txt">'
        'Download text tree (.txt)</a></p>'
    )
    text_body = text_body.replace("<pre><code>", download_link + "<pre><code>", 1)
    write(CONFIG["documents"]["text_tree"]["output"], page(text_title, f'<article class="document">{text_body}</article>', text_title))


def build_analytics() -> None:
    source = ROOT / "apps/analytics-dashboard/dist"
    target = DIST / "analytics/app"
    shutil.copytree(source, target)
    # The embedded Data app recognizes *.chatgpt.site as a hosted dashboard and
    # reads these same-origin endpoints. This static site packages equivalent
    # read-only responses alongside the immutable dashboard snapshot.
    manifest_path = source / "data-app-build.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        snapshot = (source / manifest["snapshot"]["path"]).read_text(encoding="utf-8")
    else:
        snapshot = (ROOT / "apps/analytics-dashboard/src/data.json").read_text(encoding="utf-8")
    write("api/snapshot", snapshot)
    write("api/presentation", json.dumps({"presentation": {}, "revision": 0, "canEdit": False}) + "\n")
    body = '''<section class="tool-page"><h1>Genealogy analytics</h1><iframe src="/analytics/app/index.html" title="Genealogy analytics dashboard"></iframe></section>'''
    write("analytics/index.html", page("Genealogy analytics", body, "Genealogy analytics"))


def build_download() -> None:
    source = ROOT / "artifacts/exports/merged_muszyna_family_tree.ged"
    copy_file(source, DIST / "download/merged_muszyna_family_tree.ged")
    title, introduction = markdown(read(CONFIG["documents"]["download"]["source"]))
    body = f'''<article class="document">{introduction}</article><div class="single-link"><a class="section-card section-card--record" href="/download/merged_muszyna_family_tree.ged" download>GEDCOM export</a></div>'''
    write(CONFIG["documents"]["download"]["output"], page(title, body, title))


def build_story() -> None:
    history = ROOT / "docs/history"
    copy_file(history / "Bronislaw.jpg", DIST / "assets/history/Bronislaw.jpg")
    copy_file(history / "BronislawCard.png", DIST / "assets/history/BronislawCard.png")
    doc_page(
        CONFIG["documents"]["story"]["source"],
        CONFIG["documents"]["story"]["output"],
        link_map={"Bronislaw.jpg": "/assets/history/Bronislaw.jpg", "BronislawCard.png": "/assets/history/BronislawCard.png"},
    )


def photo_slug(filename: str) -> str:
    readable = unicodedata.normalize("NFKD", Path(filename).stem).encode("ascii", "ignore").decode()
    readable = re.sub(r"[^a-z0-9]+", "-", readable.lower()).strip("-")[:70] or "photo"
    return readable + "-" + hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12]


def image_files(directory: Path) -> list[Path]:
    suffixes = {".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
    if not directory.is_dir():
        raise FileNotFoundError(f"Photo collection unavailable: {directory}. Check website/site.json and the linked drive.")
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in suffixes)


def image_gallery(
    source_dir: Path,
    asset_dir: str,
    title: str,
    output: str,
    *,
    convert: bool = False,
    detail_pages: bool = False,
    gallery_class: str = "",
) -> dict[str, str]:
    files = image_files(source_dir)
    cards: list[str] = []
    mapping: dict[str, str] = {}
    photos: list[tuple[Path, str, str]] = []
    for index, source in enumerate(files, 1):
        if convert or source.suffix.lower() in {".tif", ".tiff"}:
            name = photo_slug(source.name) + ".jpg"
            target = DIST / asset_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((1600, 2400))
                image.save(target, "JPEG", quality=90)
        else:
            name = source.name
            target = DIST / asset_dir / name
            copy_file(source, target)
        url = "/" + asset_dir + "/" + quote(name)
        detail_url = f"/america/photos/{photo_slug(source.name)}/" if detail_pages else url
        mapping[source.name] = detail_url
        photos.append((source, url, detail_url))
        caption = html.escape(source.stem)
        original_pdf = source.with_suffix(".pdf")
        if not convert and original_pdf.is_file():
            pdf_name = original_pdf.name
            copy_file(original_pdf, DIST / asset_dir / pdf_name)
            pdf_url = "/" + asset_dir + "/" + quote(pdf_name)
            caption += f'<br><a href="{pdf_url}" download>Download original scan (PDF)</a>'
        cards.append(f'''<figure class="media-card photo"><a href="{detail_url}"><img src="{url}" alt="{html.escape(source.stem, quote=True)}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>''')
    class_name = f"media-grid photos {gallery_class}".strip()
    body = f'<section class="page-title"><h1>{html.escape(title)}</h1></section><section class="collection"><div class="{class_name}">{"".join(cards)}</div></section>'
    write(output, page(title, body, title))
    if detail_pages:
        for index, (source, url, _detail_url) in enumerate(photos):
            links = []
            if index > 0:
                links.append(f'<a href="{photos[index - 1][2]}">Previous</a>')
            links.append('<a href="/america/photos/">All photos</a>')
            if index + 1 < len(photos):
                links.append(f'<a href="{photos[index + 1][2]}">Next</a>')
            filename = html.escape(source.stem)
            detail = f'''<article class="photo-detail"><h1>{filename}</h1><figure><img src="{url}" alt="{html.escape(source.stem, quote=True)}"><figcaption><span>File name</span>{filename}</figcaption></figure><nav class="photo-nav" aria-label="Photograph navigation">{"".join(links)}</nav></article>'''
            write(f"america/photos/{photo_slug(source.name)}/index.html", page(source.stem, detail, title))
    return mapping


def america_link_map() -> dict[str, str]:
    directory = ROOT / CONFIG["collections"]["america"]["directory"]
    return {f"../../media/SophieJoseph/{path.name}": f"/america/photos/{photo_slug(path.name)}/" for path in image_files(directory)}


def build_legacy_photo_links() -> None:
    for number, filename in CONFIG["legacy_photo_urls"].items():
        url = f"/america/photos/{photo_slug(filename)}/"
        if not (DIST / url.lstrip("/") / "index.html").is_file():
            raise FileNotFoundError(f"Published photo is missing: {filename}. Update legacy_photo_urls explicitly if intentionally removed.")
        redirect = page("Photograph moved", f'<p><a href="{url}">View photograph</a></p>')
        redirect = redirect.replace("</head>", f'<meta http-equiv="refresh" content="0;url={url}"></head>')
        write(f"america/photos/{number}/index.html", redirect)


def build_america() -> None:
    image_gallery(ROOT / CONFIG["collections"]["america"]["directory"], "assets/photos/sophie-joseph", "Joseph and Sophie in America — photographs", "america/photos/index.html", convert=True, detail_pages=True, gallery_class="america-photos")
    timeline = ROOT / CONFIG["timeline"]
    copy_file(timeline, DIST / "assets/america" / timeline.name)
    link_map = america_link_map()
    link_map["./" + timeline.name] = "/assets/america/" + quote(timeline.name)
    title, content = markdown(read(CONFIG["documents"]["america"]["source"]), link_map)
    gallery_link = '<p class="gallery-entry"><a class="section-card section-card--memory" href="/america/photos/">Family documents and photographs</a></p>'
    content = content.replace("</h1>", f"</h1>{gallery_link}", 1)
    body = f'''<article class="document">{content}</article>'''
    write(CONFIG["documents"]["america"]["output"], page("Joseph and Sophie in America", body, title))


def build_assets() -> None:
    for asset in (ROOT / "website/templates").iterdir():
        if asset.suffix in {".css", ".js", ".svg"}:
            copy_file(asset, DIST / "assets" / asset.name)


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    build_assets()
    build_home()
    build_sources()
    build_names()
    build_tree()
    build_analytics()
    build_download()
    build_story()
    image_gallery(ROOT / CONFIG["collections"]["muszyna"]["directory"], "assets/photos/muszyna", "Pictures from Muszyna", "photos/index.html")
    build_america()
    build_legacy_photo_links()
    print(f"Built {sum(1 for path in DIST.rglob('*') if path.is_file())} files in {DIST}")


if __name__ == "__main__":
    main()
