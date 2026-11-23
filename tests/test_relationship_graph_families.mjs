import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const template = readFileSync(new URL('../scripts/templates/cytoscape_genealogy_graph.html', import.meta.url), 'utf8');
const projection = template.slice(template.indexOf('  function familyGraphElements'), template.indexOf('  function connectedComponents()'));
const sourceFilter = template.slice(template.indexOf('  function familyForSource'), template.indexOf('  function selectedRoles'));
const family = (id, father_id, mother_id, children) => ({ id, father_id, mother_id, children });

test('shared adults and competing parent records keep distinct family connections', () => {
  const people = new Map(['a', 'b', 'c', 'd', 'e'].map(id => [id, id]));
  const records = [
    family('1', 'a', '', ['c', 'c', 'e']),
    family('2', 'b', '', ['c']),
    family('3', 'c', 'd', ['e']),
    family('4', 'c', '', []),
  ];
  const context = { people, fullName: id => id, lastName: id => id, familyHeading: f => f.id, generationLabel: () => 'Generation unplaced' };
  runInNewContext(projection, context);
  const { nodes, edges } = context.familyGraphElements(records);
  assert.deepEqual(Array.from(nodes, node => node.data.id), ['f:1', 'f:2', 'f:3', 'f:4']);
  assert.equal(nodes[0].data.label, 'a · 2');
  assert.deepEqual(Array.from(edges, edge => edge.data.id).sort(), [
    'family-descent:1:3:c', 'family-descent:1:4:c',
    'family-descent:2:3:c', 'family-descent:2:4:c', 'shared-partner:3:4:c',
  ]);
});

test('a chart supporting one parent-child link does not add the second parent in Families view', () => {
  const record = { ...family('1', 'a', 'b', ['c', 'd']), generation: '4' };
  const evidence = [
    { source_id: 'S1', relationship: 'parent-child', person_id: 'a', related_person_id: 'c' },
    { source_id: 'S2', relationship: 'family' },
  ];
  const context = { evidenceFor: () => evidence };
  runInNewContext(sourceFilter, context);
  const partial = context.familyForSource(record, 'S1', true);
  assert.equal(partial.father_id, 'a');
  assert.equal(partial.mother_id, null);
  assert.deepEqual(partial.children, ['c']);
  assert.equal(partial.generation, '4');
  assert.equal(context.familyForSource(record, 'S2', true), record);
  assert.equal(context.familyForSource(record, 'S1').mother_id, 'b');
});
