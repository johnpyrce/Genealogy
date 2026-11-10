import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const template = readFileSync(new URL('../scripts/templates/cytoscape_genealogy_graph.html', import.meta.url), 'utf8');
const helpers = template.slice(template.indexOf('  function sourceIdsForPerson'), template.indexOf('  function updateColorLegend'));

function fixture(mode = 'source') {
  const context = {
    people: new Map([
      ['1', { source_ids: 'S1' }],
      ['2', { source_ids: 'S1;S7' }],
      ['3', { source_ids: '' }],
    ]),
    sourceColors: new Map([['S1', 'blue'], ['S7', 'gray']]),
    disabledColorCategories: new Set(),
    mainLineChildren: new Set(['1']),
    mainLineSpouses: new Set(['2']),
    document: { getElementById: () => ({ value: mode }) },
  };
  runInNewContext(helpers, context);
  return context;
}

test('turning off one source keeps people with another enabled citation visible', () => {
  const c = fixture();
  c.disabledColorCategories.add('source:S1');
  assert.equal(c.personCategoryVisible('1'), false);
  assert.equal(c.personCategoryVisible('2'), true);
  assert.deepEqual(Array.from(c.enabledSourceIds('2')), ['S7']);
  c.disabledColorCategories.add('source:S7');
  assert.equal(c.personCategoryVisible('2'), false);
  c.disabledColorCategories.delete('source:S1');
  assert.equal(c.personCategoryVisible('1'), true);
  assert.equal(c.personCategoryVisible('2'), true);
});

test('uncited people have their own category', () => {
  const c = fixture();
  c.disabledColorCategories.add('source:S1');
  c.disabledColorCategories.add('source:S7');
  assert.equal(c.personCategoryVisible('3'), true);
  c.disabledColorCategories.add('source:none');
  assert.equal(c.personCategoryVisible('3'), false);
});

test('lineage categories operate independently of source categories', () => {
  const c = fixture('lineage');
  c.disabledColorCategories.add('source:S1');
  c.disabledColorCategories.add('lineage:spouse');
  assert.equal(c.personCategoryVisible('1'), true);
  assert.equal(c.personCategoryVisible('2'), false);
  assert.equal(c.personCategoryVisible('3'), true);
});

test('uniform mode has an independent person category', () => {
  const c = fixture('uniform');
  c.disabledColorCategories.add('source:S1');
  assert.equal(c.personCategoryVisible('1'), true);
  c.disabledColorCategories.add('uniform:person');
  assert.equal(c.personCategoryVisible('1'), false);
});
