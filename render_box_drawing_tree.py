from __future__ import annotations

import html
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DIRECTORY = Path(__file__).resolve().parent
SOURCE = DIRECTORY / "merged_family_tree_box_drawing.md"
PNG_OUTPUT = DIRECTORY / "merged_family_tree_box_drawing.png"
SVG_OUTPUT = DIRECTORY / "merged_family_tree_box_drawing.svg"
FONT_PATH = Path("/Users/johnpyrce/Library/Fonts/JetBrainsMonoNLNerdFontMono-Regular.ttf")

BACKGROUND = "#fafaf7"
INK = "#172a2c"
MUTED = "#516567"
ACCENT = "#0f766e"
MONO_SIZE = 16
HEADING_SIZE = 24
SECTION_SIZE = 18
LINE_HEIGHT = 23
PADDING_X = 54
PADDING_Y = 46


def source_lines() -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    in_code = False
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        if line == "```text":
            in_code = True
            continue
        if line == "```":
            in_code = False
            lines.append(("gap", ""))
            continue
        if in_code:
            lines.append(("tree", line))
        elif line.startswith("# "):
            lines.append(("title", line[2:]))
        elif line.startswith("## "):
            lines.append(("section", line[3:]))
    return lines


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        raise FileNotFoundError(f"Required rendering font was not found: {path}")
    return ImageFont.truetype(str(path), size=size)


def build() -> None:
    lines = source_lines()
    mono = font(FONT_PATH, MONO_SIZE)
    heading = font(FONT_PATH, HEADING_SIZE)
    section = font(FONT_PATH, SECTION_SIZE)

    tree_width = max((mono.getlength(text) for kind, text in lines if kind == "tree"), default=0)
    canvas_width = int(tree_width + 2 * PADDING_X)
    height = PADDING_Y
    for kind, _ in lines:
        if kind == "title":
            height += HEADING_SIZE + 34
        elif kind == "section":
            height += SECTION_SIZE + 26
        elif kind == "tree":
            height += LINE_HEIGHT
        else:
            height += 18
    height += PADDING_Y

    image = Image.new("RGB", (canvas_width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    y = PADDING_Y
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{height}" viewBox="0 0 {canvas_width} {height}">',
        "<style>",
        f".title{{font-family:'JetBrainsMonoNL Nerd Font Mono','JetBrains Mono',Menlo,monospace;font-size:{HEADING_SIZE}px;font-weight:700;fill:{INK};letter-spacing:0}}",
        f".section{{font-family:'JetBrainsMonoNL Nerd Font Mono','JetBrains Mono',Menlo,monospace;font-size:{SECTION_SIZE}px;font-weight:700;fill:{ACCENT};letter-spacing:0}}",
        f".tree{{font-family:'JetBrainsMonoNL Nerd Font Mono','JetBrains Mono',Menlo,monospace;font-size:{MONO_SIZE}px;fill:{INK};letter-spacing:0;font-variant-ligatures:none}}",
        "</style>",
        f'<rect width="100%" height="100%" fill="{BACKGROUND}"/>',
    ]

    for kind, text in lines:
        if kind == "title":
            draw.text((PADDING_X, y), text, font=heading, fill=INK)
            svg_lines.append(f'<text class="title" x="{PADDING_X}" y="{y + HEADING_SIZE}">{html.escape(text)}</text>')
            y += HEADING_SIZE + 34
        elif kind == "section":
            draw.text((PADDING_X, y), text, font=section, fill=ACCENT)
            svg_lines.append(f'<text class="section" x="{PADDING_X}" y="{y + SECTION_SIZE}">{html.escape(text)}</text>')
            y += SECTION_SIZE + 26
        elif kind == "tree":
            draw.text((PADDING_X, y), text, font=mono, fill=INK, spacing=0)
            svg_lines.append(
                f'<text class="tree" x="{PADDING_X}" y="{y + MONO_SIZE}" xml:space="preserve">{html.escape(text)}</text>'
            )
            y += LINE_HEIGHT
        else:
            y += 18

    svg_lines.append("</svg>")
    image.save(PNG_OUTPUT, optimize=True)
    SVG_OUTPUT.write_text("\n".join(svg_lines), encoding="utf-8")
    print(f"Rendered {len(lines)} lines to {PNG_OUTPUT.name} and {SVG_OUTPUT.name}")


if __name__ == "__main__":
    build()
