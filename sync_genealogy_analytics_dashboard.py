"""Refresh the HTML report's reviewed data from the DuckDB analytics database."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from build_genealogy_analytics import DEFAULT_DATABASE, DIRECTORY, analytics_queries, query_rows, supplemental_queries


DEFAULT_DASHBOARD_DATA = DIRECTORY / "genealogy-statistics-report" / "src" / "data.json"
SOURCE_FILES = [
    "genealogy_people_registry.csv",
    "genealogy_family_registry.csv",
    "genealogy_relationship_evidence.csv",
    "genealogy_sources.csv",
    "genealogy_analytics.duckdb",
]


def source(label: str, component_ids: list[str], definition: str) -> dict[str, Any]:
    return {
        "label": label,
        "sourceFiles": SOURCE_FILES,
        "filters": ["Rebuilt from the editable CSV registries through the local DuckDB analytical layer"],
        "metricDefinitions": [{"label": label, "definition": definition, "componentIds": component_ids}],
    }


def metric_map(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {row["measure"]: row["value"] for row in rows}


def reviewed_queries(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    domains = {name: query_rows(connection, sql) for name, sql in analytics_queries().items()}
    inventory = metric_map(domains["inventory"])
    tree = metric_map(domains["tree_structure"])
    return {
        "summary": {
            "rows": [{
                "people": inventory["People"], "families": inventory["Families"],
                "familyChildMemberships": inventory["Family-child memberships"],
                "parentChildEdges": inventory["Directed parent-child links"],
                "evidenceRecords": inventory["Evidence records"], "sourceCharts": inventory["Source charts"],
                "maximumGeneration": tree["Maximum generation"], "components": tree["Connected components"],
            }],
            "source": source("DuckDB analytics summary", ["analytics-summary", "metric-people", "metric-generation", "metric-families", "metric-sources"], "Headline inventory and tree-structure measures calculated from normalized DuckDB tables."),
        },
        "inventory": {"rows": domains["inventory"], "source": source("Registry inventory", ["inventory-chart", "inventory-table"], "Counts at their natural registry grain; parent-child edges are directed.")},
        "completeness": {"rows": domains["completeness"], "source": source("Registry completeness", ["completeness-chart", "completeness-table"], "Known values divided by the stated people or family denominator.")},
        "evidence": {"rows": domains["evidence"], "source": source("Evidence confidence", ["evidence-confidence-chart"], "Confidence labels on evidence rows, not a score for every distinct relationship.")},
        "source_contribution": {
            "rows": query_rows(connection, "SELECT source_id AS sourceId, COUNT(*)::BIGINT AS evidenceRecords FROM relationship_evidence GROUP BY source_id ORDER BY evidenceRecords DESC, sourceId"),
            "source": source("Evidence contribution by source chart", ["evidence-source-chart"], "Evidence-row counts by stable source-chart identifier."),
        },
        "tree_structure": {"rows": domains["tree_structure"], "source": source("Computed tree structure", ["tree-structure-table"], "Structure computed from documented parent-child edges; spouses are excluded.")},
        "family_structure": {"rows": domains["family_structure"], "source": source("Recorded family structure", ["family-structure-table"], "Recorded registry structure; missing partners or children are not evidence of absence.")},
        "temporal": {
            "rows": [{"decade": f"{int(row['decade'])}s", "people": row["people_with_recorded_birth"]} for row in domains["temporal"]],
            "source": source("Recorded births by decade", ["temporal-chart"], "People grouped by recorded birth decade; undated people are excluded."),
        },
        "names_and_identity": {
            "rows": [{"familyName": row["family_name_group"], "people": row["people"]} for row in domains["names_and_identity"]],
            "source": source("Normalized family-name groups", ["family-name-chart", "family-name-table"], "Registry family-name groups as recorded and normalized in the people registry."),
        },
        "family_size_distribution": {"rows": query_rows(connection, supplemental_queries()["family_size_distribution"]), "source": source("Family-size distribution", ["family-size-chart"], "Children listed per family, excluding families with no recorded children.")},
        "longevity_distribution": {
            "rows": [{"ageBand": f"{int(row['age_band_start'])}–{int(row['age_band_start']) + 9}", "people": row["people"]} for row in query_rows(connection, supplemental_queries()["longevity_distribution"])],
            "source": source("Age-at-death distribution", ["longevity-chart"], "Recorded death year minus recorded birth year; only people with both years are included."),
        },
        "child_birth_span_distribution": {"rows": query_rows(connection, supplemental_queries()["child_birth_span_distribution"]), "source": source("Child birth-year span by family", ["child-birth-span-chart"], "Earliest to latest recorded child birth year within families with at least two dated children.")},
        "parent_age_distribution": {"rows": query_rows(connection, supplemental_queries()["parent_age_distribution"]), "source": source("Parent age at child's birth", ["parent-age-chart"], "Child birth year minus parent birth year for parent-child links with both years recorded.")},
        "top_first_names": {
            "rows": [{"firstName": row["first_name"], "people": row["people"]} for row in query_rows(connection, supplemental_queries()["top_first_names"])],
            "source": source("Most common recorded first names", ["first-name-chart"], "Distinct person-registry entries grouped by the recorded first name."),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--dashboard-data", type=Path, default=DEFAULT_DASHBOARD_DATA)
    parser.add_argument("--build-status", choices=("updating", "complete"), default="complete",
                        help="Dashboard authoring status to write after a successful data sync.")
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit(f"Database not found: {args.database}. Run build_genealogy_analytics.py first.")

    existing = json.loads(args.dashboard_data.read_text(encoding="utf-8"))
    connection = duckdb.connect(str(args.database), read_only=True)
    try:
        existing["queries"] = reviewed_queries(connection)
    finally:
        connection.close()
    existing.update({
        "title": "The Muszyna genealogy has nine documented generations",
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "buildStatus": args.build_status,
        "status": "reviewed",
    })
    args.dashboard_data.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Synced {args.dashboard_data} from {args.database.name}")


if __name__ == "__main__":
    main()
