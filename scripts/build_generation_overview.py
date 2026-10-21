"""Build an offline, interactive surname and generation overview."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import duckdb

from scripts.build_genealogy_analytics import create_tables, query_rows
from scripts.lib.genealogy_data import ROOT, load_people


def build_data() -> dict:
    """Reuse analytics generation semantics and count unique registry people."""
    with duckdb.connect(':memory:') as connection:
        create_tables(connection)
        generations = {
            row['person_id']: row['generation']
            for row in query_rows(connection, 'SELECT * FROM person_generation')
        }
        families = connection.execute('SELECT COUNT(*) FROM families').fetchone()[0]
    people = [dict(person, generation=generations[person['id']]) for person in load_people()]
    counts = Counter(person['surname_group'] for person in people)
    return {
        'people': people,
        'groups': sorted(counts, key=lambda group: (-counts[group], group)),
        'generations': max(generations.values(), default=0),
        'families': families,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'artifacts/interactive/generation_overview.html')
    args = parser.parse_args()
    payload = json.dumps(build_data(), ensure_ascii=False).replace('<', '\\u003c')
    template = (ROOT / 'scripts/templates/generation_overview.html').read_text(encoding='utf-8')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace('__OVERVIEW_DATA__', payload), encoding='utf-8')
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    main()
