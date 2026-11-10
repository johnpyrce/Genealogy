import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../website/templates/site.js', import.meta.url), 'utf8');

function fixture({ overFrame = true, overGraph = true, loaded = true, handled = true } = {}) {
  let listener;
  const forwarded = [];
  const canvas = {};
  const graph = {
    contains: target => target === canvas,
    dispatchEvent(event) {
      forwarded.push(event);
      if (handled) event.defaultPrevented = true;
    },
  };
  const frame = {
    clientLeft: 0, clientTop: 1,
    getBoundingClientRect: () => ({ left: 20, top: 100 }),
    contentDocument: loaded ? {
      getElementById: () => graph,
      elementFromPoint(x, y) {
        assert.equal(x, 200);
        assert.equal(y, 300);
        return overGraph ? canvas : {};
      },
    } : null,
    contentWindow: { WheelEvent: class {
      constructor(type, options) { this.type = type; Object.assign(this, options); }
    } },
  };
  runInNewContext(script, {
    document: {
      querySelector: selector => selector.startsWith('iframe') ? frame : null,
      elementFromPoint: () => overFrame ? frame : {},
    },
    window: { addEventListener(type, callback, options) {
      assert.equal(type, 'wheel');
      assert.equal(options.passive, false);
      listener = callback;
    } },
  });
  const event = {
    // The event can target the outer document; only pointer coordinates matter.
    target: {}, clientX: 220, clientY: 401,
    deltaY: -3, deltaX: 0, deltaZ: 0, deltaMode: 1, ctrlKey: true,
    defaultPrevented: false, stopped: false,
    preventDefault() { this.defaultPrevented = true; },
    stopImmediatePropagation() { this.stopped = true; },
  };
  return { run: () => listener(event), event, forwarded };
}

test('a wheel event retained by the outer page reaches the chart with iframe coordinates', () => {
  const { run, event, forwarded } = fixture();
  run();
  assert.equal(forwarded.length, 1);
  assert.equal(forwarded[0].clientX, 200);
  assert.equal(forwarded[0].clientY, 300);
  assert.equal(forwarded[0].deltaMode, 1);
  assert.equal(forwarded[0].deltaY, -3);
  assert.equal(forwarded[0].ctrlKey, true);
  assert.equal(event.defaultPrevented, true);
  assert.equal(event.stopped, true);
});

for (const [name, options] of [
  ['page outside the iframe', { overFrame: false }],
  ['chart overlay or details panel', { overGraph: false }],
  ['iframe before loading', { loaded: false }],
]) {
  test(`leaves scrolling alone over ${name}`, () => {
    const { run, event, forwarded } = fixture(options);
    run();
    assert.equal(forwarded.length, 0);
    assert.equal(event.defaultPrevented, false);
  });
}

test('allows scrolling when the chart declines wheel handling', () => {
  const { run, event } = fixture({ handled: false });
  run();
  assert.equal(event.defaultPrevented, false);
});
