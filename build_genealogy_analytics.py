"""Build reproducible DuckDB genealogy analytics from the editable CSV registries.

The CSV files remain the source of truth.  This script recreates a local,
ignored DuckDB database with normalized relationship tables, then writes the
seven agreed reporting domains to a reviewable JSON result.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import duckdb

from genealogy_data import DIRECTORY


DEFAULT_DATABASE = DIRECTORY / "genealogy_analytics.duckdb"
DEFAULT_OUTPUT = DIRECTORY / "genealogy_analytics.json"
SCHEMA_VERSION = 1


def query_rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    """Return a query result as JSON-ready dictionaries."""
    result = connection.execute(sql)
    columns = [column[0] for column in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def create_tables(connection: duckdb.DuckDBPyConnection) -> None:
    """Load the registries and expose relationship tables at analytical grain."""
    for table in (
        "people", "families", "sources", "relationship_evidence", "family_children",
        "parent_child", "partner_associations", "person_generation", "person_component",
    ):
        connection.execute(f"DROP TABLE IF EXISTS {table}")

    csv_files = {
        "people": DIRECTORY / "genealogy_people_registry.csv",
        "families": DIRECTORY / "genealogy_family_registry.csv",
        "sources": DIRECTORY / "genealogy_sources.csv",
        "relationship_evidence": DIRECTORY / "genealogy_relationship_evidence.csv",
    }
    for table, csv_file in csv_files.items():
        connection.execute(
            f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto(?, header = true)",
            [str(csv_file)],
        )

    connection.execute(
        """
        CREATE TABLE family_children AS
        SELECT
            families.id::INTEGER AS family_id,
            child_id::INTEGER AS child_id,
            families.branch_role,
            families.note AS family_note
        FROM families
        CROSS JOIN UNNEST(string_split(families.children_ids, ';')) AS child(child_id)
        WHERE child_id <> ''
        """
    )
    connection.execute(
        """
        CREATE TABLE parent_child AS
        SELECT fc.family_id, f.father_id::INTEGER AS parent_id, fc.child_id, 'father' AS parent_role
        FROM families f JOIN family_children fc ON fc.family_id = f.id::INTEGER
        WHERE f.father_id IS NOT NULL
        UNION ALL
        SELECT fc.family_id, f.mother_id::INTEGER AS parent_id, fc.child_id, 'mother' AS parent_role
        FROM families f JOIN family_children fc ON fc.family_id = f.id::INTEGER
        WHERE f.mother_id IS NOT NULL
        """
    )
    connection.execute(
        """
        CREATE TABLE partner_associations AS
        SELECT id::INTEGER AS family_id, father_id::INTEGER AS person_id, mother_id::INTEGER AS partner_id
        FROM families
        WHERE father_id IS NOT NULL AND mother_id IS NOT NULL
        UNION ALL
        SELECT id::INTEGER AS family_id, mother_id::INTEGER AS person_id, father_id::INTEGER AS partner_id
        FROM families
        WHERE father_id IS NOT NULL AND mother_id IS NOT NULL
        """
    )
    create_person_generations(connection)


def create_person_generations(connection: duckdb.DuckDBPyConnection) -> None:
    """Compute longest-path generations and undirected components from parent-child edges."""
    people = [row["id"] for row in query_rows(connection, "SELECT id::INTEGER AS id FROM people")]
    edges = query_rows(
        connection,
        "SELECT DISTINCT parent_id, child_id FROM parent_child WHERE parent_id <> child_id",
    )
    children: dict[int, set[int]] = defaultdict(set)
    adjacency: dict[int, set[int]] = defaultdict(set)
    in_degree = {person_id: 0 for person_id in people}
    for edge in edges:
        parent_id, child_id = edge["parent_id"], edge["child_id"]
        if child_id not in children[parent_id]:
            children[parent_id].add(child_id)
            adjacency[parent_id].add(child_id)
            adjacency[child_id].add(parent_id)
            in_degree[child_id] += 1

    # Kahn's traversal permits a child with two named parents while preserving
    # the longest documented descent path. It fails loudly on a cyclic registry
    # rather than returning an arbitrary generation value.
    roots = sorted(person_id for person_id, degree in in_degree.items() if degree == 0)
    generation = {root: 1 for root in roots}
    queue: deque[int] = deque(roots)
    processed = 0
    while queue:
        person_id = queue.popleft()
        processed += 1
        for child_id in children.get(person_id, set()):
            generation[child_id] = max(generation.get(child_id, 1), generation[person_id] + 1)
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)
    if processed != len(people):
        raise ValueError("Cannot compute generations: parent-child registry contains a cycle")

    connection.execute("CREATE TABLE person_generation (person_id INTEGER, generation INTEGER)")
    connection.executemany(
        "INSERT INTO person_generation VALUES (?, ?)",
        sorted(generation.items()),
    )
    components: list[tuple[int, int]] = []
    unvisited = set(people)
    component_id = 0
    while unvisited:
        component_id += 1
        seed = min(unvisited)
        component_queue = deque([seed])
        unvisited.remove(seed)
        while component_queue:
            person_id = component_queue.popleft()
            components.append((person_id, component_id))
            for neighbor in adjacency[person_id]:
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    component_queue.append(neighbor)
    connection.execute("CREATE TABLE person_component (person_id INTEGER, component_id INTEGER)")
    connection.executemany("INSERT INTO person_component VALUES (?, ?)", components)


def analytics_queries() -> dict[str, str]:
    """Stable SQL definitions for the agreed report domains."""
    return {
        "inventory": """
            SELECT 'People' AS measure, COUNT(*)::BIGINT AS value FROM people
            UNION ALL SELECT 'Families', COUNT(*) FROM families
            UNION ALL SELECT 'Partner associations', COUNT(DISTINCT family_id) FROM partner_associations
            UNION ALL SELECT 'Family-child memberships', COUNT(*) FROM family_children
            UNION ALL SELECT 'Directed parent-child links', COUNT(*) FROM parent_child
            UNION ALL SELECT 'Source charts', COUNT(*) FROM sources
            UNION ALL SELECT 'Evidence records', COUNT(*) FROM relationship_evidence
        """,
        "completeness": """
            WITH measures AS (
                SELECT 'First name' AS field, COUNT(*) FILTER (WHERE first_name <> '')::BIGINT AS known, COUNT(*)::BIGINT AS total FROM people
                UNION ALL SELECT 'Surname', COUNT(*) FILTER (WHERE surname <> ''), COUNT(*) FROM people
                UNION ALL SELECT 'Family-name group', COUNT(*) FILTER (WHERE family_name_group <> ''), COUNT(*) FROM people
                UNION ALL SELECT 'Birth year', COUNT(*) FILTER (WHERE birth_year IS NOT NULL), COUNT(*) FROM people
                UNION ALL SELECT 'Death year', COUNT(*) FILTER (WHERE death_year IS NOT NULL), COUNT(*) FROM people
                UNION ALL SELECT 'Both birth and death', COUNT(*) FILTER (WHERE birth_year IS NOT NULL AND death_year IS NOT NULL), COUNT(*) FROM people
                UNION ALL SELECT 'Named parent', COUNT(DISTINCT child_id), (SELECT COUNT(*) FROM people) FROM parent_child
                UNION ALL SELECT 'Recorded partner', COUNT(DISTINCT person_id), (SELECT COUNT(*) FROM people) FROM partner_associations
                UNION ALL SELECT 'Generation assigned', COUNT(*), (SELECT COUNT(*) FROM people) FROM person_generation
                UNION ALL SELECT 'Family evidence', COUNT(DISTINCT family_id), (SELECT COUNT(*) FROM families) FROM relationship_evidence
            )
            SELECT field, known, total, ROUND(100.0 * known / total, 1) AS coverage_pct
            FROM measures
            ORDER BY field
        """,
        "evidence": """
            SELECT
                confidence,
                COUNT(*)::BIGINT AS evidence_records,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct
            FROM relationship_evidence
            GROUP BY confidence
            ORDER BY CASE confidence WHEN 'confirmed' THEN 1 WHEN 'probable' THEN 2 WHEN 'uncertain' THEN 3 ELSE 4 END
        """,
        "tree_structure": """
            SELECT 'Connected components' AS measure, COUNT(DISTINCT component_id)::BIGINT AS value FROM person_component
            UNION ALL SELECT 'Roots', COUNT(*)
            FROM people p WHERE NOT EXISTS (SELECT 1 FROM parent_child pc WHERE pc.child_id = p.id)
            UNION ALL SELECT 'Terminal lines', COUNT(*) FROM people p WHERE NOT EXISTS (SELECT 1 FROM parent_child pc WHERE pc.parent_id = p.id)
            UNION ALL SELECT 'Maximum generation', MAX(generation) FROM person_generation
            UNION ALL SELECT 'Maximum generation width', MAX(width) FROM (SELECT generation, COUNT(*) AS width FROM person_generation GROUP BY generation)
            UNION ALL SELECT 'Isolated people', COUNT(*) FROM people p WHERE NOT EXISTS (SELECT 1 FROM parent_child pc WHERE pc.parent_id = p.id OR pc.child_id = p.id)
        """,
        "family_structure": """
            WITH child_counts AS (
                SELECT f.id::INTEGER AS family_id, COUNT(fc.child_id)::BIGINT AS children
                FROM families f LEFT JOIN family_children fc ON fc.family_id = f.id
                GROUP BY f.id
            )
            SELECT 'Families with recorded children' AS measure, COUNT(*) FILTER (WHERE children > 0)::BIGINT AS value FROM child_counts
            UNION ALL SELECT 'Mean children per family with children', ROUND(AVG(children) FILTER (WHERE children > 0), 2) FROM child_counts
            UNION ALL SELECT 'Median children per family with children', MEDIAN(children) FILTER (WHERE children > 0) FROM child_counts
            UNION ALL SELECT 'Largest recorded family', MAX(children) FROM child_counts
        """,
        "temporal": """
            SELECT
                FLOOR(birth_year / 10) * 10 AS decade,
                COUNT(*)::BIGINT AS people_with_recorded_birth
            FROM people
            WHERE birth_year IS NOT NULL
            GROUP BY decade
            ORDER BY decade
        """,
        "names_and_identity": """
            SELECT family_name_group, COUNT(*)::BIGINT AS people
            FROM people
            GROUP BY family_name_group
            ORDER BY people DESC, family_name_group
        """,
    }


def supplemental_queries() -> dict[str, str]:
    """Distribution queries used by the HTML report but not its seven domain catalog."""
    return {
        "family_size_distribution": """
            WITH child_counts AS (
                SELECT f.id::INTEGER AS family_id, COUNT(fc.child_id)::INTEGER AS children
                FROM families f LEFT JOIN family_children fc ON fc.family_id = f.id::INTEGER
                GROUP BY f.id
            )
            SELECT children AS family_size, COUNT(*)::BIGINT AS families
            FROM child_counts WHERE children > 0
            GROUP BY children ORDER BY family_size
        """,
        "longevity_distribution": """
            WITH lifespans AS (
                SELECT death_year - birth_year AS age
                FROM people
                WHERE birth_year IS NOT NULL AND death_year IS NOT NULL
            )
            SELECT FLOOR(age / 10) * 10 AS age_band_start, COUNT(*)::BIGINT AS people
            FROM lifespans
            GROUP BY age_band_start ORDER BY age_band_start
        """,
        "child_birth_span_distribution": """
            WITH family_spans AS (
                SELECT fc.family_id, MAX(p.birth_year) - MIN(p.birth_year) AS span_years
                FROM family_children fc JOIN people p ON p.id = fc.child_id
                WHERE p.birth_year IS NOT NULL
                GROUP BY fc.family_id
                HAVING COUNT(*) >= 2
            )
            SELECT
                CASE
                    WHEN span_years < 5 THEN '0–4 years'
                    WHEN span_years < 10 THEN '5–9 years'
                    WHEN span_years < 15 THEN '10–14 years'
                    WHEN span_years < 20 THEN '15–19 years'
                    ELSE '20+ years'
                END AS span_band,
                CASE
                    WHEN span_years < 5 THEN 1
                    WHEN span_years < 10 THEN 2
                    WHEN span_years < 15 THEN 3
                    WHEN span_years < 20 THEN 4
                    ELSE 5
                END AS sort_order,
                COUNT(*)::BIGINT AS families
            FROM family_spans
            GROUP BY span_band, sort_order
            ORDER BY sort_order
        """,
        "parent_age_distribution": """
            WITH parent_ages AS (
                SELECT p_child.birth_year - p_parent.birth_year AS age
                FROM parent_child pc
                JOIN people p_parent ON p_parent.id = pc.parent_id
                JOIN people p_child ON p_child.id = pc.child_id
                WHERE p_parent.birth_year IS NOT NULL AND p_child.birth_year IS NOT NULL
            )
            SELECT
                CASE
                    WHEN age < 20 THEN 'Under 20'
                    WHEN age < 25 THEN '20–24'
                    WHEN age < 30 THEN '25–29'
                    WHEN age < 35 THEN '30–34'
                    WHEN age < 40 THEN '35–39'
                    ELSE '40 and over'
                END AS age_band,
                CASE
                    WHEN age < 20 THEN 1
                    WHEN age < 25 THEN 2
                    WHEN age < 30 THEN 3
                    WHEN age < 35 THEN 4
                    WHEN age < 40 THEN 5
                    ELSE 6
                END AS sort_order,
                COUNT(*)::BIGINT AS parent_child_observations
            FROM parent_ages
            GROUP BY age_band, sort_order
            ORDER BY sort_order
        """,
        "top_first_names": """
            SELECT first_name AS first_name, COUNT(*)::BIGINT AS people
            FROM people
            WHERE first_name <> ''
            GROUP BY first_name
            ORDER BY people DESC, first_name
            LIMIT 10
        """,
    }


def build_output(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Create a documented JSON artifact from the normalized database."""
    definitions = {
        "inventory": "Counts at their natural registry grain; a parent-child edge is directed.",
        "completeness": "Known values divided by all people (or all families for family evidence).",
        "evidence": "Evidence-row confidence, not a confidence score for every distinct relationship.",
        "tree_structure": "Computed from documented parent-child edges; spouses are excluded.",
        "family_structure": "Recorded registry structure; missing children or partners are not proof of absence.",
        "temporal": "Recorded birth years by decade; undated people are excluded.",
        "names_and_identity": "Normalized family-name groups; variants remain as recorded unless normalized in the registry.",
    }
    display = {
        "inventory": "horizontal bar chart and summary table",
        "completeness": "sorted horizontal bar chart with percentage labels",
        "evidence": "stacked bar chart plus source-contribution table",
        "tree_structure": "metric cards plus generation-width bar chart",
        "family_structure": "metric table and child-count distribution",
        "temporal": "column chart by birth decade",
        "names_and_identity": "ranked horizontal bar chart with searchable table",
    }
    queries = analytics_queries()
    return {
        "schema_version": SCHEMA_VERSION,
        "source_of_truth": "Editable CSV registries in this repository",
        "database": DEFAULT_DATABASE.name,
        "normalized_tables": [
            "people", "families", "sources", "relationship_evidence", "family_children",
            "parent_child", "partner_associations", "person_generation", "person_component",
        ],
        "domains": [
            {"id": domain, "definition": definitions[domain], "recommended_display": display[domain], "rows": query_rows(connection, sql)}
            for domain, sql in queries.items()
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="Ignored DuckDB database to recreate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Reviewable analytics JSON output.")
    args = parser.parse_args()

    connection = duckdb.connect(str(args.database))
    try:
        create_tables(connection)
        output = build_output(connection)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        domain_rows = {domain["id"]: len(domain["rows"]) for domain in output["domains"]}
        print(f"Built {args.database.name} and {args.output.name}: {domain_rows}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
