"""Render a Markdown genealogy report from the DuckDB analytical database."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import duckdb

from scripts.build_genealogy_analytics import DEFAULT_DATABASE, ROOT, analytics_queries, query_rows, supplemental_queries


DEFAULT_OUTPUT = ROOT / "artifacts" / "analytics" / "genealogy_analytics_report.md"
DEFAULT_TITLE = "Genealogy analytics report"


def display_value(value: Any) -> str:
    """Format report values without adding false precision."""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    """Render a compact Markdown table."""
    lines = [f"| {' | '.join(headers)} |", f"| {' | '.join('---' for _ in headers)} |"]
    lines.extend(f"| {' | '.join(display_value(value) for value in row)} |" for row in rows)
    return lines


def metric_values(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {row["measure"]: row["value"] for row in rows}


def render_report(connection: duckdb.DuckDBPyConnection, title: str = DEFAULT_TITLE) -> str:
    """Create an evidence-aware, reader-friendly Markdown report from DuckDB."""
    domains = {domain: query_rows(connection, sql) for domain, sql in analytics_queries().items()}
    inventory = metric_values(domains["inventory"])
    structure = metric_values(domains["tree_structure"])
    family = metric_values(domains["family_structure"])
    source_contribution = query_rows(
        connection,
        """
        SELECT source_id, COUNT(*)::BIGINT AS evidence_records
        FROM relationship_evidence
        GROUP BY source_id
        ORDER BY evidence_records DESC, source_id
        """,
    )
    oldest_people = query_rows(connection, supplemental_queries()["oldest_people"])

    lines = [
        f"# {title}",
        "",
        "## Executive summary",
        "",
        f"- **{inventory['People']} people** are represented in **{inventory['Families']} family records**.",
        f"- The normalized relationship model contains **{inventory['Family-child memberships']} family-child memberships** and **{inventory['Directed parent-child links']} directed parent-child links**.",
        f"- The longest documented parent-child path reaches **{structure['Maximum generation']} generations**; the registry has **{structure['Connected components']} connected components** when spouses are excluded.",
        f"- **{inventory['Evidence records']} evidence records** cite **{inventory['Source charts']} original source charts**.",
        "",
        "## Inventory",
        "",
        *markdown_table(["Measure", "Count"], [[row["measure"], row["value"]] for row in domains["inventory"]]),
        "",
        "## Completeness",
        "",
        "Coverage uses the stated denominator for each measure. Family evidence is measured against family records; all other rows are measured against people.",
        "",
        *markdown_table(
            ["Field", "Known", "Total", "Coverage"],
            [[row["field"], row["known"], row["total"], f"{row['coverage_pct']:.1f}%"] for row in domains["completeness"]],
        ),
        "",
        "## Evidence",
        "",
        "Confidence is assigned to evidence rows, not necessarily to every distinct parent-child relationship.",
        "",
        *markdown_table(
            ["Confidence", "Evidence records", "Share"],
            [[row["confidence"].title(), row["evidence_records"], f"{row['share_pct']:.1f}%"] for row in domains["evidence"]],
        ),
        "",
        "### Evidence contribution by source chart",
        "",
        *markdown_table(["Source", "Evidence records"], [[row["source_id"], row["evidence_records"]] for row in source_contribution]),
        "",
        "## Tree structure",
        "",
        "Tree-structure measures use documented parent-child edges only; spouses are excluded.",
        "",
        *markdown_table(["Measure", "Value"], [[row["measure"], row["value"]] for row in domains["tree_structure"]]),
        "",
        "## Family structure",
        "",
        "Recorded partners and children describe the registry, not the complete historical household record.",
        "",
        *markdown_table(["Measure", "Value"], [[row["measure"], row["value"]] for row in domains["family_structure"]]),
        "",
        "## Temporal coverage",
        "",
        "Only people with a recorded birth year contribute to this distribution.",
        "",
        *markdown_table(
            ["Birth decade", "People with recorded birth"],
            [[f"{int(row['decade'])}s", row["people_with_recorded_birth"]] for row in domains["temporal"]],
        ),
        "",
        "## Names and identity",
        "",
        "The leading normalized family-name groups are shown below. Full rows remain available in `artifacts/analytics/genealogy_analytics.json` and the DuckDB `people` table.",
        "",
        *markdown_table(
            ["Family-name group", "People"],
            [[row["family_name_group"], row["people"]] for row in domains["names_and_identity"][:15]],
        ),
        "",
        "## Method and limitations",
        "",
        "The editable CSV registries are the source of truth. This report is rendered from normalized DuckDB tables rebuilt from those registries. Missing names, dates, partners, children, and relationships are missing observations—not evidence that they did not exist. Generation is the longest documented acyclic parent-child path, and a cycle causes the analytical build to fail rather than silently assigning an arbitrary level.",
        "",
        "## Oldest people with recorded birth years",
        "",
        "This list contains the ten earliest recorded birth years. People without a recorded birth year are excluded; a recorded year may be approximate where noted.",
        "",
        *markdown_table(
            ["Person", "Birth year", "Death year", "Note"],
            [[row["person_name"], row["birth_year"], row["death_year"] or "—", row["note"] or "—"] for row in oldest_people],
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="Existing DuckDB database to render from.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Markdown report to write.")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Report title.")
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit(f"Database not found: {args.database}. Run build_genealogy_analytics.py first.")

    connection = duckdb.connect(str(args.database), read_only=True)
    try:
        report = render_report(connection, args.title)
    finally:
        connection.close()
    args.output.write_text(report, encoding="utf-8")
    print(f"Rendered {args.output.name} from {args.database.name}")


if __name__ == "__main__":
    main()
