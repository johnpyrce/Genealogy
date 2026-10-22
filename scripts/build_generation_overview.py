"""Build an offline, interactive surname and generation overview."""
from __future__ import annotations

import argparse
from collections import Counter, deque
import json
from pathlib import Path

from scripts.lib.genealogy_data import ROOT, load_families, load_people


def generation_layout(people: list[dict], families: list[tuple]) -> dict:
    """Align exact family steps in both directions within connected components.

    The largest component is the reference family (ties use the lowest person ID).
    Zero means unaligned, never an inferred generation. A contradictory component
    is left entirely unaligned so traversal order cannot choose an account.
    """
    links = {person['id']: [] for person in people}

    def connect(a: int, b: int, step: int, family_id: int) -> None:
        links[a].append((b, step, family_id))
        links[b].append((a, -step, family_id))

    for family_id, (father, mother, children, _) in enumerate(families, 1):
        if father is not None and mother is not None:
            connect(father, mother, 0, family_id)
        for parent in (father, mother):
            if parent is not None:
                for child in children:
                    connect(parent, child, 1, family_id)

    components = []
    seen = set()
    for person_id in sorted(links):
        if person_id in seen:
            continue
        levels = {person_id: 0}
        ready = deque([person_id])
        conflicts = set()
        while ready:
            current = ready.popleft()
            for other, step, family_id in links[current]:
                expected = levels[current] + step
                if other not in levels:
                    levels[other] = expected
                    ready.append(other)
                elif levels[other] != expected:
                    conflicts.add(family_id)
        seen.update(levels)
        components.append({'levels': levels, 'conflicts': sorted(conflicts)})
    components.sort(key=lambda component: (-len(component['levels']), min(component['levels'])))
    placements = {}
    for index, component in enumerate(components):
        levels = component['levels']
        status = 'conflict' if component['conflicts'] else ('aligned' if index == 0 else 'disconnected')
        offset = 1 - min(levels.values())
        for person_id, level in levels.items():
            placements[person_id] = {
                'generation': level + offset if status == 'aligned' else 0,
                'alignment': status,
                'component': min(levels),
                'conflicting_families': component['conflicts'],
            }
    return placements


def build_data() -> dict:
    """Align families for display and count unique registry people."""
    registry_people = load_people()
    families = load_families()
    placements = generation_layout(registry_people, families)
    people = [dict(person, **placements[person['id']]) for person in registry_people]
    counts = Counter(person['surname_group'] for person in people)
    return {
        'people': people,
        'groups': sorted(counts, key=lambda group: (-counts[group], group)),
        'generations': max((p['generation'] for p in people), default=0),
        'families': len(families),
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
