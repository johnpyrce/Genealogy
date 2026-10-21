"""Date markup shared by website generation and publication staging."""
from datetime import date, datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo


def current_publication_date() -> date:
    return datetime.now(ZoneInfo("America/Chicago")).date()


def publication_date_html(value: date) -> str:
    label = f"{value.strftime('%B')} {value.day}, {value.year}"
    return f'<time data-publication-date datetime="{value.isoformat()}">{label}</time>'


def stamp_publication_date(directory: Path, value: date) -> None:
    """Stamp the publication copy without changing the reviewed local build."""
    for page in directory.rglob("*.html"):
        original = page.read_text(encoding="utf-8")
        updated = re.sub(r'<time data-publication-date datetime="[^"]*">[^<]*</time>',
                         publication_date_html(value), original)
        if updated != original:
            page.write_text(updated, encoding="utf-8")
