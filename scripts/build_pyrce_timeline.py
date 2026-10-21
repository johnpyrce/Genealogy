"""Draw a vertical two-lane timeline from the Joseph and Sophie events CSV."""
from __future__ import annotations

import argparse
import csv
from html import escape
from pathlib import Path
import textwrap

from scripts.lib.genealogy_data import ROOT


def build(source: Path, output: Path) -> None:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        events = list(csv.DictReader(handle))
    for event in events:
        if event["Who"] not in {"Joseph", "Sophie", "Both"}:
            raise ValueError(f"Unknown lane: {event['Who']}")
        int(event["Date"])
    events.sort(key=lambda event: int(event["Date"]))
    if not events:
        raise ValueError("The events CSV is empty.")
    colors = {"Joseph": "#246577", "Sophie": "#9b574b", "Both": "#756846"}
    rails = {"Joseph": 600, "Sophie": 1200}
    first_year = int(events[0]["Date"])
    last_year = int(events[-1]["Date"])
    pixels_per_year = 24
    top = 90
    bottom = top + (last_year - first_year) * pixels_per_year
    height = bottom + 45

    def year_y(year: int) -> int:
        return top + (year - first_year) * pixels_per_year

    def label_baselines(who: str, offset: int) -> dict[int, float]:
        # Pool crowded labels, balancing displacement around their true years.
        indices = [i for i, event in enumerate(events) if event["Who"] == who]
        label_gap = 56
        blocks = []
        for order, index in enumerate(indices):
            target = year_y(int(events[index]["Date"])) + offset
            blocks.append(([order], target - order * label_gap))
            while len(blocks) > 1 and blocks[-2][1] > blocks[-1][1]:
                right_orders, right_mean = blocks.pop()
                left_orders, left_mean = blocks.pop()
                orders = left_orders + right_orders
                mean = (len(left_orders) * left_mean + len(right_orders) * right_mean) / len(orders)
                blocks.append((orders, mean))
        return {indices[order]: mean + order * label_gap
                for orders, mean in blocks for order in orders}

    shared_baselines = label_baselines("Both", -12)
    individual_baselines = {**label_baselines("Joseph", 10), **label_baselines("Sophie", 10)}

    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"
      viewBox="0 0 1800 {height}" preserveAspectRatio="xMidYMid meet"
      role="img" aria-labelledby="title description">
      <title id="title">Joseph and Sophie Pyrce: two lives, one family</title>
      <desc id="description">Two vertical timelines with one linear year scale.
      Joseph appears on the left and Sophie on the right. Shared events connect
      both lines. Shared annotations are displaced slightly when needed, with
      angled connectors preserving the exact year positions of their event dots.
      Disputed and possible accounts retain their source qualifications.</desc>
      <style>text{{font-family:Arial,Helvetica,sans-serif;fill:#253439}}
      .small{{font-size:21px;fill:#657174}}
      .name{{font-family:Georgia,serif;font-size:36px}}
      .event{{font-size:30px}}
      .year{{font-weight:700}}</style>
      <rect width="1800" height="{height}" fill="#faf8f2"/>
      <text x="350" y="45" text-anchor="middle" class="name" style="fill:{colors['Joseph']}">Joseph Pyrce</text>
      <text x="1450" y="45" text-anchor="middle" class="name" style="fill:{colors['Sophie']}">Sophie Pyrce</text>''']
    for year in range((first_year // 10 + 1) * 10, last_year + 1, 10):
        y = year_y(year)
        parts.append(f'<line x1="95" x2="1740" y1="{y}" y2="{y}" stroke="#deded4" stroke-width="1"/>')
        parts.append(f'<text x="75" y="{y + 6}" text-anchor="end" class="small">{year}</text>')
    for who, x in rails.items():
        years = [int(event["Date"]) for event in events if event["Who"] in (who, "Both")]
        if years:
            parts.append(f'<line x1="{x}" x2="{x}" y1="{year_y(min(years))}" y2="{year_y(max(years))}" stroke="{colors[who]}" stroke-opacity=".55" stroke-width="7"/>')
    nodes = set()
    for event_index, event in enumerate(events):
        who = event["Who"]
        color = colors[who]
        year = int(event["Date"])
        y = year_y(year)
        label = event["Event"].replace("(displuted)", "(disputed)")
        if who == "Both":
            tx, ty, anchor = 900, shared_baselines[event_index], "middle"
            connector_y = ty + 13
            parts.append(f'<path d="M 600 {y} H 635 L 675 {connector_y} H 1125 L 1165 {y} H 1200" fill="none" stroke="{color}" stroke-width="1.5"/>')
        elif who == "Joseph":
            tx, ty, anchor = 570, individual_baselines[event_index], "end"
            parts.append(f'<path d="M 600 {y} L 582 {ty - 10}" fill="none" stroke="{color}" stroke-width="1.5"/>')
        else:
            tx, ty, anchor = 1230, individual_baselines[event_index], "start"
            parts.append(f'<path d="M 1200 {y} L 1218 {ty - 10}" fill="none" stroke="{color}" stroke-width="1.5"/>')
        # Longer individual accounts may use two lines to retain a large font.
        lines = [label] if who == "Both" else textwrap.wrap(
            label, width=35, break_long_words=False, break_on_hyphens=False)
        ty -= (len(lines) - 1) * 18
        parts.append(f'<text x="{tx}" y="{ty}" text-anchor="{anchor}" class="event"><tspan class="year" fill="{color}">{year}</tspan> · {escape(lines[0])}')
        for line in lines[1:]:
            parts.append(f'<tspan x="{tx}" dy="36">{escape(line)}</tspan>')
        parts.append('</text>')
        for person, rail in rails.items():
            if who in (person, "Both") and (person, year) not in nodes:
                parts.append(f'<circle cx="{rail}" cy="{y}" r="6" fill="{colors[person]}" stroke="#faf8f2" stroke-width="2"/>')
                nodes.add((person, year))
    parts.append('</svg>')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {output} ({len(events)} events)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/sections/pyrce_events.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/sections/joseph_sophie_timeline_vertical.svg")
    args = parser.parse_args()
    build(args.source, args.output)


if __name__ == "__main__":
    main()
