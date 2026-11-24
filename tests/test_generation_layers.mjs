import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../scripts/templates/generation_layers.js', import.meta.url), 'utf8');
const { layoutGenerationLayers, separateProjectedNodes, traceGenerations } = runInNewContext(
  script + '\n({layoutGenerationLayers, separateProjectedNodes, traceGenerations});'
);

test('spouses align front to back while both sibling rows stay intact', () => {
  const people = Array.from({ length: 11 }, (_, i) => ({
    id: i + 1,
    component_generation: i < 4 ? 1 : i < 10 ? 2 : 3,
  }));
  const families = [
    { id: 1, parents: [1, 2], children: [5, 6] },
    { id: 2, parents: [3, 4], children: [7, 8] },
    { id: 3, parents: [5, 7], children: [11] },
    { id: 4, parents: [5, 9], children: [] },
    { id: 5, parents: [5, 10], children: [] },
  ];
  const { positions } = layoutGenerationLayers(people, families);
  for (const [first, second] of [[5, 6], [7, 8]]) {
    assert.equal(positions.get(first).z, positions.get(second).z);
    assert.ok(positions.get(first).x < positions.get(second).x);
  }
  const anchor = positions.get(5);
  const partnerDepths = [7, 9, 10].map(id => {
    const spouse = positions.get(id);
    assert.equal(spouse.x, anchor.x);
    assert.equal(spouse.y, anchor.y);
    return spouse.z;
  });
  assert.equal(new Set([...partnerDepths, anchor.z]).size, 4);
  assert.ok(positions.get(1).y > anchor.y && anchor.y > positions.get(11).y);
  assert.equal(positions.size, people.length);
});

test('projected people stay visible and individually selectable when their positions coincide', () => {
  const points = Array.from({length: 50}, (_, id) => ({id, x: 18, y: 20}));
  const gap = 10;
  const placed = separateProjectedNodes(points, 220, 180, gap);
  assert.deepEqual(Array.from(placed, point => point.id), points.map(point => point.id));
  for (let i = 0; i < placed.length; i++) {
    const {x, y, anchorX, anchorY} = placed[i];
    assert.equal(anchorX, points[i].x);
    assert.equal(anchorY, points[i].y);
    assert.ok(x >= 7 && x <= 213 && y >= 7 && y <= 173);
    assert.ok(placed.slice(0, i).every(other => Math.hypot(x - other.x, y - other.y) >= gap));
  }
});

test('ancestor tracing retains shared and unequal-length paths and terminates on a cycle', () => {
  const parents = new Map([[1, [2, 3]], [2, [4]], [3, [5]], [5, [4]], [4, [6]], [6, [4]]]);
  const {distance, reverse} = traceGenerations(1, parents);
  assert.equal(distance.get(4), 2);
  assert.equal(distance.size, 6);
  assert.deepEqual([...reverse.get(4)], [2, 5, 6]);
  const path = traceGenerations(5, reverse);
  assert.deepEqual([...path.distance.keys()], [5, 3, 1]);
  assert.equal(traceGenerations(99, parents).distance.size, 1);
});
