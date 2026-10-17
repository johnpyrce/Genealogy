#!/usr/bin/env python3
"""Build the static Our Polish Family History site from repository sources."""

from __future__ import annotations

import html
import base64
from io import BytesIO
import json
import re
import shutil
import hashlib
import unicodedata
from string import Template
from PIL import Image, ImageOps
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree


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
        label, url, new_tab = match.group(1), match.group(2).strip("<>"), match.group(3)
        url = link_map.get(url, url)
        attributes = ' target="_blank" rel="noopener"' if new_tab else ""
        return hold(f'<a href="{html.escape(url, quote=True)}"{attributes}>{html.escape(label)}</a>')

    text = re.sub(r"!\[([^]]*)\]\(([^)]+)\)", image, text)
    text = re.sub(r'\[([^]]+)\]\(([^)]+)\)(\{target="_blank"\})?', link, text)
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
  <a class="brand" href="/">Our Polish Family History</a>
  <button class="menu-button" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
  <nav id="site-nav" class="site-nav" aria-label="Primary navigation">{links}</nav>
</header>'''


def footer() -> str:
    return '''<footer class="site-footer"><span>By John Pyrce · October 2, 2026</span><a href="mailto:rekarpyrce@gmail.com">Comments</a></footer>'''


def page(title: str, body: str, description: str = "Our Polish Family History") -> str:
    template = Template((ROOT / "website/templates/page.html").read_text(encoding="utf-8"))
    stylesheet_version = hashlib.sha256((ROOT / "website/templates/site.css").read_bytes()).hexdigest()[:12]
    icon_version = hashlib.sha256((ROOT / "website/templates/favicon.svg").read_bytes()).hexdigest()[:12]
    site_title = "Our Polish Family History"
    browser_title = site_title if not title or title == site_title else f"{title} · {site_title}"
    return template.substitute(description=html.escape(description, quote=True),
                               title=html.escape(browser_title), header=header(), body=body, footer=footer(),
                               stylesheet_version=stylesheet_version, icon_version=icon_version)


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


def card_index(title: str, links: list[tuple[str, str]], output: str, introduction: str = "") -> None:
    cards = "".join(section_card(href, label) for href, label in links)
    body = f'<section class="page-title"><h1>{html.escape(title)}</h1>{introduction}</section><nav class="section-grid" aria-label="{html.escape(title)}">{cards}</nav>'
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
    body = f'<article class="document intro">{intro}</article><section class="index"><nav class="section-grid" aria-label="Explore the archive">{links}</nav></section>'
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
    ], "names/index.html", '<p>These pages explain the Gościński, Pyrć/Pyrc, and Pyrce names. '
       'Histories of the Miczulski and Rams surnames have not yet been added.</p>')
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
        body = (f'<section class="tool-page"><h1>{label}</h1>'
                f'<p class="tool-actions"><a href="{src}" target="_blank" rel="noopener">Open {label.lower()} in a full window</a>'
                ' · <a href="/tree/">Choose another tree view</a></p>'
                f'<iframe src="{src}" title="{label}"></iframe></section>')
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
    body = f'''<article class="document">{introduction}</article>
<nav class="section-grid" aria-label="Download and reading options">
<a class="section-card section-card--record" href="/download/merged_muszyna_family_tree.ged" download>Download GEDCOM (.ged)</a>
<a class="section-card section-card--record" href="/tree/text/family_tree.txt" download>Download text family tree (.txt)</a>
<a class="section-card section-card--record" href="/tree/text/">Read the text tree online</a>
</nav>'''
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


def linked_video_files(directory: Path) -> list[tuple[str, str]]:
    """Return catalog titles and Google Drive links from synced .gvid references."""
    videos = []
    for reference in sorted(directory.glob("*.gvid")):
        try:
            metadata = json.loads(reference.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid Google video reference: {reference}") from exc
        document_id = metadata.get("doc_id")
        if not isinstance(document_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", document_id):
            raise ValueError(f"Google video reference has no valid doc_id: {reference}")
        title = reference.stem.replace(" - ", " — ")
        url = f"https://docs.google.com/videos/d/{document_id}/edit"
        videos.append((title, url))
    return videos


def image_gallery(
    source_dir: Path,
    asset_dir: str,
    title: str,
    output: str,
    *,
    convert: bool = False,
    detail_pages: bool = False,
    gallery_class: str = "",
    description_html: str = "",
    first_photo: str | None = None,
    photo_credits: dict[str, dict[str, str]] | None = None,
    photo_captions: dict[str, str] | None = None,
    photo_notes: dict[str, str] | None = None,
    linked_videos: list[tuple[str, str]] | None = None,
) -> dict[str, str]:
    files = image_files(source_dir)
    if first_photo:
        featured = next((source for source in files if source.name == first_photo), None)
        if featured is None:
            raise FileNotFoundError(f"First gallery photo is missing: {first_photo}")
        files.remove(featured)
        files.insert(0, featured)
    photo_credits = photo_credits or {}
    photo_captions = photo_captions or {}
    photo_notes = photo_notes or {}

    def display_caption(source: Path) -> str:
        return photo_captions.get(source.name, source.stem.strip())

    def credit_for(source: Path) -> str:
        credit = photo_credits.get(source.name)
        if not credit:
            return ""
        return (f'Photo source: <a href="{html.escape(credit["url"], quote=True)}" '
                f'target="_blank" rel="noopener">{html.escape(credit["name"])}</a>')

    gallery_path = Path(output).parent
    gallery_url = "/" if gallery_path == Path(".") else f"/{gallery_path.as_posix()}/"
    cards: list[str] = []
    mapping: dict[str, str] = {}
    photos: list[tuple[Path, str, str]] = []
    for index, source in enumerate(files, 1):
        converted = convert or source.suffix.lower() in {".tif", ".tiff"}
        if converted:
            name = photo_slug(source.name) + ".jpg"
            target = DIST / asset_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source) as original:
                image = ImageOps.exif_transpose(original)
                if image.mode.startswith("I;16"):
                    # Direct RGB conversion clips 16-bit scans to nearly all white.
                    image = image.convert("I").point(lambda value: value / 257).convert("L")
                image = image.convert("RGB")
                # Preserve the scan dimensions for the full-size viewing link.
                image.save(target, "JPEG", quality=90)
        else:
            name = source.name
            target = DIST / asset_dir / name
            copy_file(source, target)
        url = "/" + asset_dir + "/" + quote(name)
        if converted:
            # Refresh converted images when their bytes change without moving photo pages.
            url += "?v=" + hashlib.sha256(target.read_bytes()).hexdigest()[:12]
        detail_url = f"{gallery_url}{photo_slug(source.name)}/" if detail_pages else url
        mapping[source.name] = detail_url
        photos.append((source, url, detail_url))
        caption = html.escape(display_caption(source))
        if note := photo_notes.get(source.name):
            caption += f'<br><span class="photo-note">{html.escape(note)}</span>'
        if credit := credit_for(source):
            caption += f"<br>{credit}"
        original_pdf = source.with_suffix(".pdf")
        if not convert and original_pdf.is_file():
            pdf_name = original_pdf.name
            copy_file(original_pdf, DIST / asset_dir / pdf_name)
            pdf_url = "/" + asset_dir + "/" + quote(pdf_name)
            caption += f'<br><a href="{pdf_url}" download>Download original scan (PDF)</a>'
        cards.append(f'''<figure class="media-card photo"><a href="{detail_url}"><img src="{url}" alt="{html.escape(display_caption(source), quote=True)}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>''')
    class_name = f"media-grid photos {gallery_class}".strip()
    description = f'<div class="gallery-intro">{description_html}</div>' if description_html else ""
    if linked_videos:
        catalog = [(source.name, card) for source, card in zip(files, cards)]
        catalog.extend(
            (label.replace(" — ", " - ") + ".gvid", f'<figure class="media-card video"><a class="video-preview" '
             f'href="{html.escape(url, quote=True)}" target="_blank" rel="noopener" '
             f'aria-label="Watch {html.escape(label, quote=True)} in Google Drive">'
             '<span class="video-play" aria-hidden="true">▶</span><span>Watch video</span></a>'
             f'<figcaption>{html.escape(label)}<br><span class="photo-note">'
             'Sophie visits Betty.  Opens in Google Drive.</span></figcaption></figure>')
            for label, url in linked_videos
        )
        cards = [card for _, card in sorted(catalog, key=lambda item: item[0])]
    body = f'<section class="page-title"><h1>{html.escape(title)}</h1></section><section class="collection">{description}<div class="{class_name}">{"".join(cards)}</div></section>'
    write(output, page(title, body, title))
    if detail_pages:
        for index, (source, url, _detail_url) in enumerate(photos):
            links = []
            if index > 0:
                links.append(f'<a href="{photos[index - 1][2]}">Previous</a>')
            links.append(f'<a href="{gallery_url}">All photos</a>')
            if index + 1 < len(photos):
                links.append(f'<a href="{photos[index + 1][2]}">Next</a>')
            filename = html.escape(source.name)
            caption = html.escape(display_caption(source))
            credit = credit_for(source)
            credit = f'<p class="photo-credit">{credit}</p>' if credit else ""
            note = photo_notes.get(source.name)
            note = f'<p class="photo-note">{html.escape(note)}</p>' if note else ""
            story_link = '<a href="/america/">Return to the America story</a>' if gallery_url == '/america/photos/' else '<a href="/america/photos/">Documents and photographs from America</a>'
            detail = f'''<article class="photo-detail"><h1>{caption}</h1><figure><img src="{url}" alt="{html.escape(display_caption(source), quote=True)}"><figcaption><span>Original file</span>{filename}</figcaption></figure>{note}{credit}<p><a href="{url}" target="_blank" rel="noopener">Open full-size image</a> · <a href="{url}" download>Download image</a></p><nav class="photo-nav" aria-label="Photograph navigation">{"".join(links)}</nav><p>{story_link}</p></article>'''
            write((gallery_path / photo_slug(source.name) / "index.html").as_posix(), page(display_caption(source), detail, title))
    return mapping


def america_link_map() -> dict[str, str]:
    directory = ROOT / CONFIG["collections"]["america"]["directory"]
    mapping = {}
    for path in image_files(directory):
        source = f"../../media/SophieJoseph/{path.name}"
        destination = f"/america/photos/{photo_slug(path.name)}/"
        mapping[source] = destination
        mapping[quote(source, safe="/")] = destination
    return mapping


def build_legacy_photo_links() -> None:
    for number, filename in CONFIG["legacy_photo_urls"].items():
        url = f"/america/photos/{photo_slug(filename)}/"
        if not (DIST / url.lstrip("/") / "index.html").is_file():
            raise FileNotFoundError(f"Published photo is missing: {filename}. Update legacy_photo_urls explicitly if intentionally removed.")
        redirect = page("Photograph moved", f'<p><a href="{url}">View photograph</a></p>')
        redirect = redirect.replace("</head>", f'<meta http-equiv="refresh" content="0;url={url}"></head>')
        write(f"america/photos/{number}/index.html", redirect)


def build_america() -> None:
    collection = CONFIG["collections"]["america"]
    image_gallery(ROOT / collection["directory"], "assets/photos/sophie-joseph", "Joseph and Sophie in America — documents and photographs", "america/photos/index.html", convert=True, detail_pages=True, gallery_class="america-photos",
                  description_html='<p><a href="/america/">Read the America story</a> · <a href="/photos/">Pictures from Muszyna</a>. Select an image to read its notes and open it full size.</p>',
                  photo_captions=collection.get("photo_captions"), photo_notes=collection.get("photo_notes"),
                  linked_videos=linked_video_files(ROOT / collection["directory"]))
    timeline = ROOT / CONFIG["timeline"]
    copy_file(timeline, DIST / "assets/america" / timeline.name)
    link_map = america_link_map()
    link_map["./" + timeline.name] = "/assets/america/" + quote(timeline.name)
    title, content = markdown(read(CONFIG["documents"]["america"]["source"]), link_map)
    timeline_image = f'<figure class="document-image"><img src="{link_map["./" + timeline.name]}"'
    content = content.replace(
        timeline_image,
        timeline_image.replace('class="document-image"', 'class="document-image document-image--timeline"'),
        1,
    )
    gallery_link = (
        '<p class="gallery-entry gallery-entry--paired">'
        '<a class="section-card section-card--memory" href="/america/photos/">Family documents and photographs</a>'
        '<a class="section-card section-card--memory" href="https://archive.pyrce.org" target="_blank" rel="noopener">Family archive</a>'
        '</p>'
    )
    content = content.replace("</h1>", f"</h1>{gallery_link}", 1)
    content = content.replace(gallery_link, gallery_link + '<p>The Family archive opens a separate, broader collection of photographs and home movies. Its access settings are separate from this site.</p>', 1)
    body = f'''<article class="document">{content}</article>'''
    write(CONFIG["documents"]["america"]["output"], page("Joseph and Sophie in America", body, title))


def build_assets() -> None:
    for asset in (ROOT / "website/templates").iterdir():
        if asset.suffix in {".css", ".js", ".svg"}:
            copy_file(asset, DIST / "assets" / asset.name)
    # The existing SVG wraps the original PNG artwork. Reuse it for browser fallbacks.
    svg = ElementTree.parse(ROOT / "website/templates/favicon.svg")
    image = svg.find("{http://www.w3.org/2000/svg}image")
    if image is None or not image.attrib.get("href", "").startswith("data:image/png;base64,"):
        raise ValueError("Favicon SVG must contain the embedded PNG artwork for icon generation.")
    with Image.open(BytesIO(base64.b64decode(image.attrib["href"].split(",", 1)[1], validate=True))) as source:
        artwork = source.convert("RGBA")
        artwork.save(DIST / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
        artwork.resize((180, 180), Image.Resampling.LANCZOS).save(DIST / "apple-touch-icon.png")
    shutil.copyfile(DIST / "apple-touch-icon.png", DIST / "apple-touch-icon-precomposed.png")


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
    muszyna_description = (
        '<p>Muszyna is a delightful small Polish spa town near Poland’s southern border with Slovakia. '
        'Explore its historic buildings, cultural sites, and surrounding scenery. '
        'Learn more on the <a href="https://muszyna.pl/" target="_blank" rel="noopener">official Muszyna city website</a> '
        'and explore videos on the <a href="https://www.youtube.com/user/muszynatv1/featured" target="_blank" rel="noopener">Muszyna.TV YouTube channel</a>. '
        '(Most browsers can translate Polish-language websites into English.)</p>'
        '<p><a href="/america/photos/">Browse documents and photographs from America</a>.</p>'
    )
    image_gallery(
        ROOT / CONFIG["collections"]["muszyna"]["directory"],
        "assets/photos/muszyna",
        "Pictures from Muszyna",
        "photos/index.html",
        detail_pages=True,
        description_html=muszyna_description,
        first_photo=CONFIG["collections"]["muszyna"].get("first_photo"),
        photo_credits=CONFIG["collections"]["muszyna"].get("photo_credits"),
        photo_captions=CONFIG["collections"]["muszyna"].get("photo_captions"),
        photo_notes=CONFIG["collections"]["muszyna"].get("photo_notes"),
    )
    build_america()
    build_legacy_photo_links()
    print(f"Built {sum(1 for path in DIST.rglob('*') if path.is_file())} files in {DIST}")


if __name__ == "__main__":
    main()
